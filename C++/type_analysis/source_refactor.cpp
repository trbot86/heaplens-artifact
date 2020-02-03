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



using namespace std;
using namespace llvm;
using namespace clang;
using namespace clang::ast_matchers;
using namespace clang::driver;
using namespace clang::tooling;

static llvm::cl::OptionCategory MatcherSampleCategory("Matcher Sample");

set<string> typenameset;

DeclarationMatcher classMatcher = 
  cxxRecordDecl(isExpansionInMainFile()).bind("class");

StatementMatcher deleteMatcher =
  cxxDeleteExpr().bind("deletecall");

StatementMatcher newMatcher =
  cxxNewExpr().bind("newcall");

StatementMatcher CStyleMallocMatcher = 
  // declRefExpr(hasDeclaration(functionDecl(hasName("malloc"))))
  // explicitCastExpr(isExpansionInMainFile(), hasDescendant(callExpr(callee(functionDecl(anyOf(hasName("malloc"), hasName("realloc"), hasName("calloc"), hasName("reallocArray"))))).bind("callex"))).bind("castex");
  explicitCastExpr(isExpansionInMainFile(), hasDescendant(declRefExpr(hasDeclaration(functionDecl(hasName("malloc")))).bind("malloc"))).bind("castex");

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
      QualType allocType = newex->getAllocatedType();
      // cout << "new: " << allocType.getAsString() << endl;
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
    CStyleAllocPrinter(Rewriter &Rewrite) : Rewrite(Rewrite) {}

    virtual void run(const MatchFinder::MatchResult &Result) {
      ASTContext* context = Result.Context;

      // const CallExpr* callex = Result.Nodes.getNodeAs<CallExpr>("callex");
      const ExplicitCastExpr* castex = Result.Nodes.getNodeAs<ExplicitCastExpr>("castex");
      const DeclRefExpr* mnode = Result.Nodes.getNodeAs<DeclRefExpr>("malloc");
      
      Rewrite.InsertTextAfterToken(mnode->getLocStart(), "<" + castex->getTypeInfoAsWritten()->getType().getAsString() + ">");

      //Print various metadata
      // cout << "malloc" << endl;
      /*cout << castex->getCastKindName() << endl;
        cout << castex->getSubExprAsWritten()->getType().getAsString() << endl;
        cout << castex->getTypeInfoAsWritten()->getType().getAsString() << endl;
        SourceLocation sl = castex->getLocStart();
        sl.dump(context->getSourceManager());
      */

    }
  
  private:
    Rewriter &Rewrite;
};

class DeleteExprPrinter : public MatchFinder::MatchCallback {
  public:
    virtual void run(const MatchFinder::MatchResult &Result) {
      const CXXDeleteExpr* delex = Result.Nodes.getNodeAs<clang::CXXDeleteExpr>("deletecall");
      QualType destroyedType = delex->getDestroyedType();
      // cout << "delete: " << destroyedType.getAsString() << endl;
    }
};

class MyASTConsumer : public ASTConsumer {
public:
  MyASTConsumer(Rewriter &R) : HandlerForAlloc(R) {
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
    Matcher.addMatcher(CStyleMallocMatcher, &HandlerForAlloc);
  }

  void HandleTranslationUnit(ASTContext &Context) override {
    // Run the matchers when we have the whole TU parsed.
    Matcher.matchAST(Context);
  }

private:
  CStyleAllocPrinter HandlerForAlloc;
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
    return llvm::make_unique<MyASTConsumer>(TheRewriter);
  }

private:
  Rewriter TheRewriter;
};

int main(int argc, const char **argv) {
  CommonOptionsParser OptionsParser(argc, argv, MatcherSampleCategory);
  
  ClangTool Tool(OptionsParser.getCompilations(),
                 OptionsParser.getSourcePathList());

  // ClassnamePrinter cp;
  // DeleteExprPrinter dp;
  // NewExprPrinter np;
  // CStyleAllocPrinter ap;

  // MatchFinder Finder;
  
  // Finder.addMatcher(classMatcher, &cp);
  // Finder.addMatcher(deleteMatcher, &dp);
  // Finder.addMatcher(newMatcher, &np);  
  // Finder.addMatcher(CStyleMallocMatcher, &ap);
  
  // Tool.run(newFrontendActionFactory(&Finder).get());
  Tool.run(newFrontendActionFactory<MyFrontendAction>().get());
  
  ofstream file;
  file.open("typedump.txt");

  for(auto i = typenameset.begin();i != typenameset.end();++i) {
    file << *i << endl;
  }

  file.close();
  return 0;
}