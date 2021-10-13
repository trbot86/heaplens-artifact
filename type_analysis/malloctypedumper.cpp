#include "memhook_interface.h"
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
 *  Matchers:
 *  match any malloc with sizeof inside as argument
 *  callExpr(callee(functionDecl(hasName("malloc"))), has(sizeOfExpr(hasType(qualType()))))
 * 
 *  
 *
 *  TODO:
 *  1) Add functionality to register new allocator/deallocator names for static analyser. (Eg. tcmalloc, jemalloc)
 *     So that type recognition functionality is not broken when new allocators are used.
*/

#include <iostream>
#include <string>
#include <bits/stdc++.h>

#include <clang/AST/AST.h>
#include <clang/AST/ASTConsumer.h>
#include <clang/ASTMatchers/ASTMatchFinder.h>
#include <clang/ASTMatchers/ASTMatchers.h>
#include <clang/Frontend/CompilerInstance.h>
#include <clang/Frontend/FrontendActions.h>
#include <clang/Tooling/CommonOptionsParser.h>
#include <clang/Tooling/JSONCompilationDatabase.h>
#include <clang/Tooling/Tooling.h>
#include <llvm/Support/raw_ostream.h>
#include <clang/AST/ExprCXX.h>
#include <clang/AST/Type.h>
#include <clang/Basic/Diagnostic.h>

#define MAX_FILE_PATH 200

using namespace std;
using namespace llvm;
using namespace clang;
using namespace clang::ast_matchers;
using namespace clang::driver;
using namespace clang::tooling;

static llvm::cl::OptionCategory MatcherSampleCategory("Matcher Sample");

map<pair<string,int>, string> malloctypeset;

void printtofile() {
  ofstream malloctypefile;
  malloctypefile.open("malloc_type_dump.txt");

  for (auto i = malloctypeset.begin(); i != malloctypeset.end(); ++i)
  {
      malloctypefile << (*i).first.first << "|" << (*i).first.second << "|" << (*i).second << endl;
  }

  malloctypefile.close();
  return;
}

set<string> typenameset;

DeclarationMatcher classMatcher =
  cxxRecordDecl(isExpansionInMainFile()).bind("class");

StatementMatcher deleteMatcher =
  cxxDeleteExpr().bind("deletecall");

StatementMatcher newMatcher =
  cxxNewExpr().bind("newcall");

StatementMatcher generalMallocMatcher =
callExpr(callee(functionDecl(hasName("malloc")))).bind("malloc");

//matches explict cast malloc expression
StatementMatcher explicitCastMallocMatcher =
  explicitCastExpr(hasDescendant(callExpr(callee(functionDecl(hasName(MTDFNAME)))).bind("expcastmalloc"))).bind("castex");

//matches sizeof within malloc without explicit casts
//***********************************************
//  Matches malloc invocations with sizeof as any sub-expressions
//  Eg. malloc(100*sizeof(int))
//***********************************************
// sizeOfExpr(hasAncestor(callExpr(callee(functionDecl(hasName("malloc")))).bind("sizeofmalloc")));
//***********************************************
//  Matches malloc invocations with sizeof as direct sub-expression
//  Eg. matches malloc(sizeof(int)) but NOT malloc(100*sizeof(int))
StatementMatcher sizeofMallocMatcher =
    expr(sizeOfExpr(allOf(hasAncestor(callExpr(callee(functionDecl(hasName(MTDFNAME)))).bind("sizeofmalloc")), \
    hasArgumentOfType(hasUnqualifiedDesugaredType(type().bind("sizeof-arg-type"))))));
//*************ASK ABOUT LONG AND UNSIGNED LONG MATCHES************ 

//matches malloc lhs without explicit casts
StatementMatcher lhsofMallocMatcher = 
 binaryOperator(hasOperatorName("="), anyOf(hasDescendant(callExpr(callee(functionDecl(hasName(MTDFNAME)))).bind("lhsmalloc")), \
 hasRHS(hasDescendant(callExpr(callee(functionDecl(hasName(MTDFNAME)))).bind("lhsmalloc")))), \
 hasLHS(hasType(type().bind("lhs-type"))));

 DeclarationMatcher declMallocMatcher =
 varDecl(hasDescendant(callExpr(callee(functionDecl(hasName(MTDFNAME)))).bind("declmalloc")), \
 hasType(type().bind("decltype")));

 void printTypetoFile(const clang::CallExpr* mnode, const clang::Type* typenode, const MatchFinder::MatchResult& Result) {
   static PrintingPolicy print_policy((Result.Context)->getLangOpts());
    print_policy.FullyQualifiedName = 1;
    print_policy.SuppressScope = 0;
    // print_policy.PrintCanonicalTypes = 1;
    
    FullSourceLoc functionDeclFullLocation = Result.Context->getFullLoc(mnode->getExprLoc());

    SmallString<MAX_FILE_PATH> pathVector;
    functionDeclFullLocation.getManager().getFileManager().makeAbsolutePath(pathVector);

    #ifdef DEBUG
    if (functionDeclFullLocation.isValid())
      // cout << "Found decl matching FunctionDecl at " << ": "<< functionDeclFullLocation.getFileEntry()->getName().str() << ":" << functionDeclFullLocation.getLineNumber() << endl;
      cout << "Found decl matching FunctionDecl at " << ": "<< pathVector.c_str() << ":" << functionDeclFullLocation.getLineNumber() << endl;

    cout << "*******SIZEOF TYPE: *******" << endl;
    typenode->dump();

    if(typenode->isBuiltinType()) {
      cout << typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy) << endl;
    }
    else if(typenode->isRecordType()) {
      cout << typenode->getAsRecordDecl()->getQualifiedNameAsString() << endl;
    }
    else if(typenode->isPointerType()) {
      cout << typenode->getPointeeType().getAsString() << endl;
    }
    cout << "*******" << endl;

    #endif

    if(typenode->isBuiltinType()) {
      malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(pathVector.c_str() + functionDeclFullLocation.getFileEntry()->getName().str(), \
      functionDeclFullLocation.getLineNumber()), typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy)));
    }
    else if(typenode->isRecordType()) {
      malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(pathVector.c_str() + functionDeclFullLocation.getFileEntry()->getName().str(), \
      functionDeclFullLocation.getLineNumber()), typenode->getAsRecordDecl()->getQualifiedNameAsString()));
    }
    else if(typenode->isPointerType()) {
      malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(pathVector.c_str() + functionDeclFullLocation.getFileEntry()->getName().str(), \
      functionDeclFullLocation.getLineNumber()), typenode->getPointeeType().getAsString()));
    }
 }

class ClassnamePrinter : public MatchFinder::MatchCallback {
  public :
    virtual void run(const MatchFinder::MatchResult &Result) {
      const RecordDecl* rd = Result.Nodes.getNodeAs<clang::RecordDecl>("class");
        typenameset.insert(rd->getDeclName().getAsString());
    }
};

class NewExprPrinter : public MatchFinder::MatchCallback {
  public:
    virtual void run(const MatchFinder::MatchResult &Result) {
      const CXXNewExpr* newex = Result.Nodes.getNodeAs<clang::CXXNewExpr>("newcall");
      /*QualType allocType =*/ newex->getAllocatedType();
      // cout << "new: " << allocType.getAsString() << endl;
    }
};

/**
 * Figure out how to get types:
 * If it is a C project, typecasts in malloc are not compulsory.
 * First check if typecast is there. If it's there, problem solved.
 * If not, check inside the malloc for sizeof() and figure out the type used.
 * Else, check the type of lhs of binary operator (if malloc is assigned to pointer)
 * Else, throw error ¯\_(ツ)_/¯
**/

//Callback for all C-Style allocation functions
class explicitCastAllocPrinter : public MatchFinder::MatchCallback {
  public:

    virtual void run(const MatchFinder::MatchResult &Result) {

      const ExplicitCastExpr* castex = Result.Nodes.getNodeAs<ExplicitCastExpr>("castex");
      const clang::CallExpr* mnode = Result.Nodes.getNodeAs<clang::CallExpr>("expcastmalloc");

      FullSourceLoc functionDeclFullLocation = Result.Context->getFullLoc(mnode->getExprLoc());

      SmallString<MAX_FILE_PATH> pathVector;
      functionDeclFullLocation.getManager().getFileManager().makeAbsolutePath(pathVector);

      #ifdef DEBUG
      //Print various metadata
      cout << "expcastmalloc" << endl;
      cout << castex->getCastKindName() << endl;
      cout << castex->getSubExprAsWritten()->getType().getAsString() << endl;
      cout << castex->getTypeAsWritten().getAsString() << endl;
      cout << castex->getTypeInfoAsWritten()->getType().getAsString() << endl;
      #endif

      malloctypeset.insert(pair<pair<string, int>, string>(pair<string, int>(pathVector.c_str() + functionDeclFullLocation.getFileEntry()->getName().str(), \
      functionDeclFullLocation.getLineNumber()), castex->getTypeInfoAsWritten()->getType().getAsString()));
    }

  private:
};

//Handler for Explicit Cast mallocs
class CStyleAllocPrinter : public MatchFinder::MatchCallback {
  public:

  virtual void run(const MatchFinder::MatchResult &Result) {
    const DeclRefExpr* mnode = Result.Nodes.getNodeAs<DeclRefExpr>("malloc");
  }

  private:
};

//Handler for sizeof malloc expressions
class sizeOfMallocPrinter : public MatchFinder::MatchCallback {
  public:

  virtual void run(const MatchFinder::MatchResult &Result) {
    const clang::CallExpr* mnode = Result.Nodes.getNodeAs<clang::CallExpr>("sizeofmalloc");
    const clang::Type* typenode = Result.Nodes.getNodeAs<clang::Type>("sizeof-arg-type");
    
    printTypetoFile(mnode, typenode, Result);

  }

  private:
};

//Handler for lhs of malloc expressions
class lhsOfMallocPrinter : public MatchFinder::MatchCallback {
  public:

  virtual void run(const MatchFinder::MatchResult &Result) {
    const clang::CallExpr* mnode = Result.Nodes.getNodeAs<clang::CallExpr>("lhsmalloc");
    const clang::Type* typenode = Result.Nodes.getNodeAs<clang::Type>("lhs-type");

    printTypetoFile(mnode, typenode, Result);
  }

  private:
};

class declMallocPrinter : public MatchFinder::MatchCallback {
  public:

  virtual void run(const MatchFinder::MatchResult &Result) {
    const clang::CallExpr* mnode = Result.Nodes.getNodeAs<clang::CallExpr>("declmalloc");
    const clang::Type* typenode = Result.Nodes.getNodeAs<clang::Type>("decltype");

    printTypetoFile(mnode, typenode, Result);
  }

  private:
};

class DeleteExprPrinter : public MatchFinder::MatchCallback {
  public:
    virtual void run(const MatchFinder::MatchResult &Result) {
      const CXXDeleteExpr* delex = Result.Nodes.getNodeAs<clang::CXXDeleteExpr>("deletecall");
      /*QualType destroyedType =*/ delex->getDestroyedType();
      // cout << "delete: " << destroyedType.getAsString() << endl;
    }
};

class MyASTConsumer : public ASTConsumer {
public:
  MyASTConsumer() {
    Matcher.addMatcher(generalMallocMatcher, &generalHandlerForAlloc);
    Matcher.addMatcher(explicitCastMallocMatcher, &explicitCastHandlerForAlloc);
    Matcher.addMatcher(sizeofMallocMatcher, &sizeOfMallocHandler);
    Matcher.addMatcher(lhsofMallocMatcher, &lhsOfMallocHandler);
    Matcher.addMatcher(declMallocMatcher, &declMallocHandler);
  }

  void HandleTranslationUnit(ASTContext &Context) override {
    // Run the matchers when we have the whole TU parsed.
    Matcher.matchAST(Context);
  }

private:
  CStyleAllocPrinter generalHandlerForAlloc;
  explicitCastAllocPrinter explicitCastHandlerForAlloc;
  sizeOfMallocPrinter sizeOfMallocHandler;
  lhsOfMallocPrinter lhsOfMallocHandler;
  declMallocPrinter declMallocHandler;
  MatchFinder Matcher;
};

class MyFrontendAction : public ASTFrontendAction {
public:
  MyFrontendAction() {}
  void EndSourceFileAction() override {
  }

  std::unique_ptr<ASTConsumer> CreateASTConsumer(CompilerInstance &CI,
                                                 StringRef file) override {
    return make_unique<MyASTConsumer>();
  }

private:
};

void typedump(char* filename) {
  ofstream file;
  file.open(filename);

  for(auto i = typenameset.begin();i != typenameset.end();++i) {
    file << *i << endl;
  }

  file.close();
}

static cl::extrahelp CommonHelp(CommonOptionsParser::HelpMessage);

int main(int argc, const char **argv) {
  string errMsg;
  auto compDatabase = JSONCompilationDatabase::loadFromFile(argv[1], errMsg, JSONCommandLineSyntax::AutoDetect);

  ClangTool Tool(*compDatabase, compDatabase->getAllFiles());

  for(const auto& src : Tool.getSourcePaths()) {
    std::cout << src << std::endl;
  }
  
  Tool.run(newFrontendActionFactory<MyFrontendAction>().get());

  printtofile();
  return 0;
}