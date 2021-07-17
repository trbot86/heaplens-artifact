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
#include <clang/Rewrite/Core/Rewriter.h>
#include <clang/Tooling/CommonOptionsParser.h>
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
  // declRefExpr(hasDeclaration(functionDecl(hasName("malloc"))))
  // explicitCastExpr(isExpansionInMainFile(), hasDescendant(callExpr(callee(functionDecl(anyOf(hasName("malloc"), hasName("realloc"), hasName("calloc"), hasName("reallocArray"))))).bind("callex"))).bind("castex");
  // explicitCastExpr(hasDescendant(declRefExpr(hasDeclaration(functionDecl(hasName("malloc")))).bind("malloc"))).bind("castex");
  explicitCastExpr(hasDescendant(callExpr(callee(functionDecl(hasName("malloc")))).bind("malloc"))).bind("castex");

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
    // sizeOfExpr(hasParent(callExpr(callee(functionDecl(hasName("malloc")))).bind("sizeofmalloc")));
    // expr(anyOf(sizeOfExpr(has(hasUnqualifiedDesugaredType(type().bind("sizeof-arg-type")))),sizeOfExpr(has(expr(hasType(hasUnqualifiedDesugaredType(type().bind("sizeof-arg-type"))))))));
    expr(sizeOfExpr(allOf(hasAncestor(callExpr(callee(functionDecl(hasName("malloc")))).bind("sizeofmalloc")), hasArgumentOfType(hasUnqualifiedDesugaredType(type().bind("sizeof-arg-type"))))));
    //*************ASK ABOUT LONG AND UNSIGNED LONG MATCHES************
    // sizeOfExpr(hasArgumentOfType(hasUnqualifiedDesugaredType(type().bind("sizeof-arg-type"))));

//matches malloc lhs without explicit casts
StatementMatcher lhsofMallocMatcher = 
// binaryOperator(hasOperatorName("="), hasRHS(ignoringImpCasts(callExpr(callee(functionDecl(hasName("malloc"))))))).bind("lhsmallocexpr");
//  binaryOperator(hasOperatorName("="), hasRHS(ignoringImpCasts(callExpr(callee(functionDecl(hasName("malloc")))).bind("rhsmalloc"))), hasLHS(hasType(type().bind("typeofnode")))).bind("lhsmallocexpr");
 binaryOperator(hasOperatorName("="), hasRHS(hasDescendant(callExpr(callee(functionDecl(hasName("malloc")))).bind("lhsmalloc"))), hasLHS(hasType(type().bind("lhs-type"))));

 DeclarationMatcher declMallocMatcher =
 varDecl(hasDescendant(callExpr(callee(functionDecl(hasName("malloc")))).bind("declmalloc")), hasType(type().bind("decltype")));

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
    explicitCastAllocPrinter(Rewriter &Rewrite) : Rewrite(Rewrite) {}

    virtual void run(const MatchFinder::MatchResult &Result) {
      //ASTContext* context = Result.Context;

      // const CallExpr* callex = Result.Nodes.getNodeAs<CallExpr>("callex");
      const ExplicitCastExpr* castex = Result.Nodes.getNodeAs<ExplicitCastExpr>("castex");
      const clang::CallExpr* mnode = Result.Nodes.getNodeAs<clang::CallExpr>("malloc");

      FullSourceLoc functionDeclFullLocation = Result.Context->getFullLoc(mnode->getExprLoc());

    //***************************************
      // Rewrite.InsertTextAfterToken(mnode->getLocStart(), "<" + castex->getTypeInfoAsWritten()->getType().getAsString() + ">");
      // Rewrite.overwriteChangedFiles();
    //***************************************

      //Print various metadata
      cout << "malloc" << endl;
      cout << castex->getCastKindName() << endl;
      cout << castex->getSubExprAsWritten()->getType().getAsString() << endl;
      cout << castex->getTypeAsWritten().getAsString() << endl;
      cout << castex->getTypeInfoAsWritten()->getType().getAsString() << endl;

      malloctypeset.insert(pair<pair<string, int>, string>(pair<string, int>(functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), castex->getTypeInfoAsWritten()->getType().getAsString()));
      // SourceLocation sl = castex->getLocStart();
      // sl.dump(context->getSourceManager());
    }

  private:
    Rewriter &Rewrite;
};

//Handler for Explicit Cast mallocs
class CStyleAllocPrinter : public MatchFinder::MatchCallback {
  public:
   CStyleAllocPrinter(Rewriter &Rewrite) : Rewrite(Rewrite) {}

  virtual void run(const MatchFinder::MatchResult &Result) {
    const DeclRefExpr* mnode = Result.Nodes.getNodeAs<DeclRefExpr>("malloc");
  }

  private:
  Rewriter& Rewrite;
};

//Handler for sizeof malloc expressions
class sizeOfMallocPrinter : public MatchFinder::MatchCallback {
  public:
   sizeOfMallocPrinter(Rewriter &Rewrite) : Rewrite(Rewrite) {}

  virtual void run(const MatchFinder::MatchResult &Result) {
    const clang::CallExpr* mallocnode = Result.Nodes.getNodeAs<clang::CallExpr>("sizeofmalloc");
    const clang::Type* typenode = Result.Nodes.getNodeAs<clang::Type>("sizeof-arg-type");
    static PrintingPolicy print_policy((Result.Context)->getLangOpts());
    print_policy.FullyQualifiedName = 1;
    print_policy.SuppressScope = 0;
    // print_policy.PrintCanonicalTypes = 1;
    
    SourceManager* SrcMgr = Result.SourceManager;
    FullSourceLoc functionDeclFullLocation = Result.Context->getFullLoc(mallocnode->getExprLoc());

    SmallString<MAX_FILE_PATH> pathVector;
    functionDeclFullLocation.getManager().getFileManager().makeAbsolutePath(pathVector);

    if (functionDeclFullLocation.isValid())
      // cout << "Found FunctionDecl at " << functionDeclFullLocation.getLineNumber() << functionDeclFullLocation.getFileEntry()->getName().str() << endl;
      // cout << "Found FunctionDecl at " << functionDeclFullLocation.getLineNumber() << functionDeclFullLocation.getManager().getFilename(functionDeclFullLocation).str() << endl;
      cout << "Found FunctionDecl at " << functionDeclFullLocation.getLineNumber() << ": "<< pathVector.c_str() << endl;

    cout << "*******SIZEOF TYPE: *******" << endl;
    typenode->dump();

    if(typenode->isBuiltinType()) {
      cout << typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy) << endl;
      // malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(pathVector.c_str() + functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy)));
      malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy)));
    }
    else if(typenode->isRecordType()) {
      cout << typenode->getAsRecordDecl()->getQualifiedNameAsString() << endl;
      // malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(pathVector.c_str() + functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), typenode->getAsRecordDecl()->getQualifiedNameAsString()));
      malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), typenode->getAsRecordDecl()->getQualifiedNameAsString()));
    }
    cout << "*******" << endl;

  }

  private:
  Rewriter& Rewrite;
};

//Handler for lhs of malloc expressions
class lhsOfMallocPrinter : public MatchFinder::MatchCallback {
  public:
   lhsOfMallocPrinter(Rewriter &Rewrite) : Rewrite(Rewrite) {}

  virtual void run(const MatchFinder::MatchResult &Result) {
    const clang::CallExpr* mnode = Result.Nodes.getNodeAs<clang::CallExpr>("lhsmalloc");
    const clang::Type* typenode = Result.Nodes.getNodeAs<clang::Type>("lhs-type");

    static PrintingPolicy print_policy((Result.Context)->getLangOpts());
    print_policy.FullyQualifiedName = 1;
    print_policy.SuppressScope = 0;
    // print_policy.PrintCanonicalTypes = 1;
    
    SourceManager* SrcMgr = Result.SourceManager;
    FullSourceLoc functionDeclFullLocation = Result.Context->getFullLoc(mnode->getExprLoc());

    SmallString<MAX_FILE_PATH> pathVector;
    functionDeclFullLocation.getManager().getFileManager().makeAbsolutePath(pathVector);

    if (functionDeclFullLocation.isValid())
      // cout << "Found FunctionDecl at " << functionDeclFullLocation.getLineNumber() << functionDeclFullLocation.getFileEntry()->getName().str() << endl;
      // cout << "Found FunctionDecl at " << functionDeclFullLocation.getLineNumber() << functionDeclFullLocation.getManager().getFilename(functionDeclFullLocation).str() << endl;
      cout << "Found lhs matching FunctionDecl at " << functionDeclFullLocation.getLineNumber() << ": "<< pathVector.c_str() << endl;

    cout << "*******SIZEOF TYPE: *******" << endl;
    typenode->dump();

    if(typenode->isBuiltinType()) {
      cout << typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy) << endl;
      // malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(pathVector.c_str() + functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy)));
      malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy)));
    }
    else if(typenode->isRecordType()) {
      cout << typenode->getAsRecordDecl()->getQualifiedNameAsString() << endl;
      // malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(pathVector.c_str() + functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), typenode->getAsRecordDecl()->getQualifiedNameAsString()));
      malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), typenode->getAsRecordDecl()->getQualifiedNameAsString()));
    }
    cout << "*******" << endl;
  }

  private:
  Rewriter& Rewrite;
};

class declMallocPrinter : public MatchFinder::MatchCallback {
  public:
   declMallocPrinter(Rewriter &Rewrite) : Rewrite(Rewrite) {}

  virtual void run(const MatchFinder::MatchResult &Result) {
    const clang::CallExpr* mnode = Result.Nodes.getNodeAs<clang::CallExpr>("declmalloc");
    const clang::Type* typenode = Result.Nodes.getNodeAs<clang::Type>("decltype");

    static PrintingPolicy print_policy((Result.Context)->getLangOpts());
    print_policy.FullyQualifiedName = 1;
    print_policy.SuppressScope = 0;
    // print_policy.PrintCanonicalTypes = 1;
    
    SourceManager* SrcMgr = Result.SourceManager;
    FullSourceLoc functionDeclFullLocation = Result.Context->getFullLoc(mnode->getExprLoc());

    SmallString<MAX_FILE_PATH> pathVector;
    functionDeclFullLocation.getManager().getFileManager().makeAbsolutePath(pathVector);

    if (functionDeclFullLocation.isValid())
      // cout << "Found FunctionDecl at " << functionDeclFullLocation.getLineNumber() << functionDeclFullLocation.getFileEntry()->getName().str() << endl;
      // cout << "Found FunctionDecl at " << functionDeclFullLocation.getLineNumber() << functionDeclFullLocation.getManager().getFilename(functionDeclFullLocation).str() << endl;
      cout << "Found decl matching FunctionDecl at " << functionDeclFullLocation.getLineNumber() << ": "<< pathVector.c_str() << endl;

    cout << "*******SIZEOF TYPE: *******" << endl;
    typenode->dump();

    if(typenode->isBuiltinType()) {
      cout << typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy) << endl;
      // malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(pathVector.c_str() + functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy)));
      malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy)));
    }
    else if(typenode->isRecordType()) {
      cout << typenode->getAsRecordDecl()->getQualifiedNameAsString() << endl;
      // malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(pathVector.c_str() + functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), typenode->getAsRecordDecl()->getQualifiedNameAsString()));
      malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), typenode->getAsRecordDecl()->getQualifiedNameAsString()));
    }
    else if(typenode->isPointerType()) {
      malloctypeset.insert(pair<pair<string,int>, string>(pair<string,int>(functionDeclFullLocation.getFileEntry()->getName().str(), functionDeclFullLocation.getLineNumber()), typenode->getPointeeType().getAsString()));
    }
    cout << "*******" << endl;
  }

  private:
  Rewriter& Rewrite;
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
  MyASTConsumer(Rewriter &R) : generalHandlerForAlloc(R), explicitCastHandlerForAlloc(R), sizeOfMallocHandler(R), lhsOfMallocHandler(R), declMallocHandler(R) {
    //**********************************************************************
    // Add a simple matcher for finding 'if' statements.
    // Matcher.addMatcher(ifStmt().bind("ifStmt"), &HandlerForAlloc);

    // Add a complex matcher for finding 'for' loops with an initializer set
    // to 0, < comparison in the codition and an increment. For example:
    //
    //  for (int i = 0; i < N; ++i)
    // Matcher.addMatcher(
    //     forStmt(hasLoopInit(declStmt(hasSingleDecl(
    //                 varDecl(hasInitializer(integerLiteral(equals(0))))
    //                     .bind("initVarName")))),
    //             hasIncrement(unaryOperator(
    //                 hasOperatorName("++"),
    //                 hasUnaryOperand(declRefExpr(to(
    //                     varDecl(hasType(isInteger())).bind("incVarName")))))),
    //             hasCondition(binaryOperator(
    //                 hasOperatorName("<"),
    //                 hasLHS(ignoringParenImpCasts(declRefExpr(to(
    //                     varDecl(hasType(isInteger())).bind("condVarName"))))),
    //                 hasRHS(expr(hasType(isInteger()))))))
    //         .bind("forLoop"),
    //     &HandlerForFor);
    //*************************************************************************

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
    TheRewriter.getEditBuffer(TheRewriter.getSourceMgr().getMainFileID())
        .write(llvm::outs());
  }

  std::unique_ptr<ASTConsumer> CreateASTConsumer(CompilerInstance &CI,
                                                 StringRef file) override {
    TheRewriter.setSourceMgr(CI.getSourceManager(), CI.getLangOpts());
    return make_unique<MyASTConsumer>(TheRewriter);
  }

private:
  Rewriter TheRewriter;
};

void typedump(char* filename) {
  ofstream file;
  file.open(filename);

  for(auto i = typenameset.begin();i != typenameset.end();++i) {
    file << *i << endl;
  }

  file.close();
}

int main(int argc, const char **argv) {
  CommonOptionsParser OptionsParser(argc, argv, MatcherSampleCategory);

  ClangTool Tool(OptionsParser.getCompilations(),
                 OptionsParser.getSourcePathList());

  // Tool.run(newFrontendActionFactory(&Finder).get());
  Tool.run(newFrontendActionFactory<MyFrontendAction>().get());

  printtofile();
  return 0;
}