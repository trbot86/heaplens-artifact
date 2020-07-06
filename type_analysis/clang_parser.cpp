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
#include <clang/AST/ExprCXX.h>
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

multimap<string, vector<string> > fieldnameset;

DeclarationMatcher classMatcher = 
  cxxRecordDecl(unless(isExpansionInSystemHeader()), unless(isTemplateInstantiation())).bind("class");

DeclarationMatcher fieldMatcher =
  fieldDecl(unless(isExpansionInSystemHeader())).bind("field");

StatementMatcher deleteMatcher =
  cxxDeleteExpr().bind("deletecall");

StatementMatcher newMatcher =
  cxxNewExpr().bind("newcall");

StatementMatcher CStyleMallocMatcher = 
  callExpr(callee(functionDecl(anyOf(hasName("malloc"), hasName("realloc"), hasName("calloc"), hasName("reallocArray")))));
  
class ClassnamePrinter : public MatchFinder::MatchCallback {
  public :
    virtual void run(const MatchFinder::MatchResult &Result) {
      const RecordDecl* rd = Result.Nodes.getNodeAs<clang::RecordDecl>("class");
        typenameset.insert(rd->getDeclName().getAsString());
        cout << endl;
        // cout << "visiting: " << rd->getDeclName().getAsString() << endl;
        cout << rd->getQualifiedNameAsString() << endl;
        auto field_iter = rd->field_begin();
        auto& context = rd->getASTContext();
        auto& rl = context.getASTRecordLayout(rd);
        // cout << rl.
        // auto& rl = (rd->getASTContext()).getASTRecordLayout(rd);

        // for(unsigned i = 0;i < rl.getFieldCount();i++) {
          // cout << rl.getFieldOffset(i) << endl;
        // }

        for(auto it = field_iter;it != rd->field_end();++it) {
          // cout << it->getType();
          // cout << it->getNameAsString() << endl;
          cout << it->getQualifiedNameAsString() << endl;
          cout << it->getASTContext().getTypeSize(it->getType())/8 << endl;
          cout << rl.getFieldOffset(it->getFieldIndex()) << endl;
          // cout << (it->getASTContext()).getTypeInfo(it->getType()).Width << endl;
          cout << it->getType().getAsString() << endl;
          fieldnameset.insert(pair<string, vector<string> >(rd->getQualifiedNameAsString(),{it->getType().getAsString(), it->getQualifiedNameAsString(), to_string(it->getASTContext().getTypeSize(it->getType())/8), to_string(rl.getFieldOffset(it->getFieldIndex())/8)}));
        }
    }
};

class NewExprPrinter : public MatchFinder::MatchCallback {
  public:
    virtual void run(const MatchFinder::MatchResult &Result) {
      const CXXNewExpr* newex = Result.Nodes.getNodeAs<clang::CXXNewExpr>("newcall");
      QualType allocType = newex->getAllocatedType();
      cout << "new: " << allocType.getAsString() << endl;
    }
};

//Callback for all C-Style allocation functions
/**
 * Figure out how to get types:
 * If it is a C++ project, typecasts in malloc are not compulsory.
 * First check if typecast is there. If it's there, problem solved.
 * If not, check the type of lhs of binary operator (if malloc is assigned to pointer)
 * Else, check inside the malloc for sizeof() and figure out the type used.
 * Else, throw error ¯\_(ツ)_/¯
**/

class CStyleAllocPrinter : public MatchFinder::MatchCallback {
  public:
    virtual void run(const MatchFinder::MatchResult &Result) {

    }
};

class DeleteExprPrinter : public MatchFinder::MatchCallback {
  public:
    virtual void run(const MatchFinder::MatchResult &Result) {
      const CXXDeleteExpr* delex = Result.Nodes.getNodeAs<clang::CXXDeleteExpr>("deletecall");
      QualType destroyedType = delex->getDestroyedType();
      cout << "delete: " << destroyedType.getAsString() << endl;
    }
};

int main(int argc, const char **argv) {
  CommonOptionsParser OptionsParser(argc, argv, MyToolCategory);
  
  ClangTool Tool(OptionsParser.getCompilations(),
                 OptionsParser.getSourcePathList());

  ClassnamePrinter cp;
  DeleteExprPrinter dp;
  NewExprPrinter np;

  MatchFinder Finder;
  
  Finder.addMatcher(classMatcher, &cp);
  // Finder.addMatcher(deleteMatcher, &dp);
  // Finder.addMatcher(newMatcher, &np);  

  Tool.run(newFrontendActionFactory(&Finder).get());
  // Tool.run(newFrontendActionFactory<SyntaxOnlyAction>().get());
  // Tool.run(newFrontendActionFactory<PreprocessOnlyAction>().get());
  
  ofstream typefile;
  typefile.open("typedump.txt");
  ofstream fieldfile;
  fieldfile.open("fielddump.txt");

  for(auto i = typenameset.begin();i != typenameset.end();++i) {
    typefile << *i << endl;
  }

  for(auto i = fieldnameset.begin();i != fieldnameset.end();++i) {
    // fieldfile << (*i).first << " | " << (*i).second.first << " | " << (*i).second.second << endl;
    fieldfile << (*i).first;
    for(auto i : (*i).second) {
      fieldfile << "|" << i;
    }
    fieldfile << endl;
  }

  typefile.close();
  fieldfile.close();

  return 0;
}