/**
 *  Basic workflow:
 *  -1) Did a basic parse of the source, printed all AST nodes
 *  and their types.
 *  -2) Did a search for all recordDecl nodes, made a list of
 *  that and printed it.
 *  -3) Looked for all new, ****malloc**** allocations and printed their
 *  types.
 *  4) Decided the layout of the typetable data structure, and
 *  how to add to it using new, malloc parsing.
 * 
 *  TODO:
 *  1) Add functionality to register new allocator/deallocator names for static analyser. (Eg. tcmalloc, jemalloc)
 *     So that type recognition functionality is not broken when new allocators are used.
*/

#include <iostream>
#include <string>
#include <bits/stdc++.h>
// #include <clang/AST/ExprCXX.h>
#include <clang/AST/Type.h>
// #include <clang/AST/ASTConsumer.h>
#include <clang/AST/ASTContext.h>
#include <clang/AST/RecordLayout.h>
// #include <clang/AST/RecursiveASTVisitor.h>
// #include <clang/Driver/Options.h>
// #include <clang/Frontend/ASTConsumers.h>
// #include <clang/Frontend/CompilerInstance.h>
#include <clang/Frontend/FrontendActions.h>
// #include <clang/Rewrite/Core/Rewriter.h>
#include <clang/Tooling/CommonOptionsParser.h>
#include <clang/Tooling/JSONCompilationDatabase.h>
#include <clang/Tooling/Tooling.h>
#include <clang/ASTMatchers/ASTMatchers.h>
#include <clang/ASTMatchers/ASTMatchFinder.h>

using namespace std;
using namespace llvm;
using namespace clang;
using namespace clang::ast_matchers;
using namespace clang::tooling;

static llvm::cl::OptionCategory MyToolCategory("my-tool options");

set<string> typenameset;
multimap<string, vector<string>> fieldnameset;

DeclarationMatcher classMatcher =
    // cxxRecordDecl(unless(isExpansionInSystemHeader()), unless(classTemplateDecl())).bind("class");
    // cxxRecordDecl(unless(isExpansionInSystemHeader()), hasDefinition(), classTemplateDecl()).bind("class");
    recordDecl(unless(isExpansionInSystemHeader())).bind("class");

class ClassnamePrinter : public MatchFinder::MatchCallback
{
public:
  virtual void run(const MatchFinder::MatchResult &Result)
  {
    const RecordDecl *rd = Result.Nodes.getNodeAs<clang::RecordDecl>("class");
    cout << "general class matcher: " << rd->getQualifiedNameAsString() << " ";
    // cout << "DCT: " << (ClassTemplateDecl *)rd->getDescribedClassTemplate() << " ";
    // cout << "TIP: " << (uint64_t)rd->getTemplateInstantiationPattern() << " ";
    // cout << "DEF: " << (uint64_t)rd->getDefinition() << " ";
    if (rd->getDefinition())
    {
      // cout << "CD: " << (uint64_t)rd->getCanonicalDecl() << " ";
      // cout << "IFMC: " << (uint64_t)rd->getInstantiatedFromMemberClass() << " ";
      // cout << "TSK: " << (uint64_t)rd->getTemplateSpecializationKind() << " ";
      // cout << "MSI: " << (uint64_t)rd->getMemberSpecializationInfo() << " ";
      // cout << "HF: " << (uint64_t)rd->hasFriends() << " ";
      // cout << "IL: " << (uint64_t)rd->isLambda() << " ";
      // cout << "ILC: " << (uint64_t)rd->isLocalClass() << " ";
      cout << "ICN: " << (uint64_t)rd->isInjectedClassName() << " ";
      cout << "IASOU: " << (uint64_t)rd->isAnonymousStructOrUnion() << " ";
      cout << "ITDAD: " << (uint64_t)rd->isThisDeclarationADefinition() << " ";
      cout << "IDT: " << (uint64_t)rd->isDependentType() << " ";
      cout << "NTPL: " << (uint64_t)rd->getNumTemplateParameterLists() << " ";
    }
    // cout << "ADB: " << (uint64_t)rd->hasAnyDependentBases() << " ";
    cout << "RD: " << (uint64_t)rd << endl;

    if (rd->getDefinition() && !rd->isDependentType())
    {
      typenameset.insert(rd->getDeclName().getAsString());
      cout << endl;
      cout << "normal class matcher: " << rd->getQualifiedNameAsString() << endl;
      auto field_iter = rd->field_begin();
      auto &context = rd->getASTContext();
      auto &rl = context.getASTRecordLayout(rd);

      for (auto it = field_iter; it != rd->field_end(); ++it)
      {
        //** cout << it->getQualifiedNameAsString() << endl;
        //** cout << it->getASTContext().getTypeSize(it->getType())/8 << endl;
        //** cout << rl.getFieldOffset(it->getFieldIndex()) << endl;
        //** cout << it->getType().getAsString() << endl;
        fieldnameset.insert(pair<string, vector<string>>(rd->getQualifiedNameAsString(), {it->getType().getAsString(), it->getQualifiedNameAsString(), to_string(it->getASTContext().getTypeSize(it->getType()) / 8), to_string(rl.getFieldOffset(it->getFieldIndex()) / 8)}));
      }
    }
  }
};

class TemplatedClassPrinter : public MatchFinder::MatchCallback
{
public:
  virtual void run(const MatchFinder::MatchResult &Result)
  {
    const NamedDecl *nd = Result.Nodes.getNodeAs<clang::NamedDecl>("templatedclass");
    cout << "templated class matcher: " << nd->getQualifiedNameAsString() << endl;
  }
};

class instTemplatedClassnamePrinter : public MatchFinder::MatchCallback
{
public:
  virtual void run(const MatchFinder::MatchResult &Result)
  {
    const RecordDecl *rd = Result.Nodes.getNodeAs<clang::RecordDecl>("insttemplatedclass");
    typenameset.insert(rd->getDeclName().getAsString());
    cout << endl;
    // cout << "visiting: " << rd->getDeclName().getAsString() << endl;
    cout << "instantiated templated class matcher: " << rd->getQualifiedNameAsString() << endl;
    auto field_iter = rd->field_begin();
    auto &context = rd->getASTContext();
    auto &rl = context.getASTRecordLayout(rd);
    // cout << rl.
    // auto& rl = (rd->getASTContext()).getASTRecordLayout(rd);

    // for(unsigned i = 0;i < rl.getFieldCount();i++) {
    // cout << rl.getFieldOffset(i) << endl;
    // }

    for (auto it = field_iter; it != rd->field_end(); ++it)
    {
      // cout << it->getType();
      // cout << it->getNameAsString() << endl;
      //** cout << it->getQualifiedNameAsString() << endl;
      //** cout << it->getASTContext().getTypeSize(it->getType())/8 << endl;
      //** cout << rl.getFieldOffset(it->getFieldIndex()) << endl;
      // cout << (it->getASTContext()).getTypeInfo(it->getType()).Width << endl;
      //** cout << it->getType().getAsString() << endl;
      fieldnameset.insert(pair<string, vector<string>>(rd->getQualifiedNameAsString(), {it->getType().getAsString(), it->getQualifiedNameAsString(), to_string(it->getASTContext().getTypeSize(it->getType()) / 8), to_string(rl.getFieldOffset(it->getFieldIndex()) / 8)}));
    }
  }
};


int main(int argc, const char **argv)
{
  string errMsg;
  auto compDatabase = JSONCompilationDatabase::loadFromFile(argv[1], errMsg, JSONCommandLineSyntax::AutoDetect);
  ClangTool Tool(*compDatabase,
                 compDatabase->getAllFiles());

  ClassnamePrinter cp;
  // TemplatedClassPrinter tcp;
  // instTemplatedClassnamePrinter itcp;

  MatchFinder Finder;

  Finder.addMatcher(classMatcher, &cp);

  const int tool_result = Tool.run(newFrontendActionFactory(&Finder).get());
  if (tool_result != 0) return tool_result;
  // Tool.run(newFrontendActionFactory<SyntaxOnlyAction>().get());
  // Tool.run(newFrontendActionFactory<PreprocessOnlyAction>().get());

  ofstream typefile;
  typefile.open("typedump.txt");
  ofstream fieldfile;
  fieldfile.open("fielddump.txt");

  for (auto i = typenameset.begin(); i != typenameset.end(); ++i)
  {
    typefile << *i << endl;
  }

  for (auto i = fieldnameset.begin(); i != fieldnameset.end(); ++i)
  {
    // fieldfile << (*i).first << " | " << (*i).second.first << " | " << (*i).second.second << endl;
    fieldfile << (*i).first;
    for (auto i : (*i).second)
    {
      fieldfile << "|" << i;
    }
    fieldfile << endl;
  }

  typefile.close();
  fieldfile.close();

  return 0;
}
