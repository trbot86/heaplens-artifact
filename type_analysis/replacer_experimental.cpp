#include <iostream>
#include <string>
#include <bits/stdc++.h>

#include <string>

#include <clang/AST/AST.h>
#include <clang/ASTMatchers/ASTMatchFinder.h>
#include <clang/ASTMatchers/ASTMatchers.h>
#include <clang/Basic/DiagnosticOptions.h>
#include <clang/Basic/FileManager.h>
#include <clang/Basic/SourceManager.h>
#include <clang/Frontend/CompilerInstance.h>
#include <clang/Frontend/FrontendActions.h>
#include <clang/Frontend/TextDiagnosticPrinter.h>
#include <clang/Rewrite/Core/Rewriter.h>
#include <clang/Format/Format.h>
#include <clang/Tooling/CommonOptionsParser.h>
//
#include <clang/Tooling/JSONCompilationDatabase.h>
#include <clang/Tooling/Inclusions/HeaderIncludes.h>
//
#include <clang/Tooling/Refactoring.h>
#include <clang/Tooling/Core/Replacement.h>
#include <clang/Tooling/Tooling.h>
#include <llvm/Support/raw_ostream.h>

using namespace clang;
using namespace clang::ast_matchers;
using namespace clang::driver;
using namespace clang::tooling;

using namespace std;

static llvm::cl::OptionCategory ToolingSampleCategory("Tooling Sample");

StatementMatcher CStyleMallocMatcher =
    // declRefExpr(hasDeclaration(functionDecl(hasName("malloc"))))
    // explicitCastExpr(isExpansionInMainFile(), hasDescendant(callExpr(callee(functionDecl(anyOf(hasName("malloc"), hasName("realloc"), hasName("calloc"), hasName("reallocArray"))))).bind("callex"))).bind("castex");
    // explicitCastExpr(hasDescendant(declRefExpr(hasDeclaration(functionDecl(hasName(MTDFNAME)))).bind("malloc"))).bind("castex");
    explicitCastExpr(hasDescendant(callExpr(callee(functionDecl(hasName(MTDFNAME)))).bind("malloc"))).bind("castex");

StatementMatcher sizeofMallocMatcher =
    expr(sizeOfExpr(allOf(hasAncestor(callExpr(callee(functionDecl(hasName(MTDFNAME)))).bind("sizeofmalloc")),
                          hasArgumentOfType(hasUnqualifiedDesugaredType(type().bind("sizeof-arg-type"))))));

//matches malloc lhs without explicit casts
StatementMatcher lhsofMallocMatcher =
    binaryOperator(hasOperatorName("="), anyOf(hasDescendant(callExpr(callee(functionDecl(hasName(MTDFNAME)))).bind("lhsmalloc")), hasRHS(hasDescendant(callExpr(callee(functionDecl(hasName(MTDFNAME)))).bind("lhsmalloc")))),
                   hasLHS(hasType(type().bind("lhs-type"))));

DeclarationMatcher declMallocMatcher =
    varDecl(hasDescendant(callExpr(callee(functionDecl(hasName(MTDFNAME)))).bind("declmalloc")),
            hasType(type().bind("decltype")));

set<pair<string, clang::SourceLocation>> replSet;
pthread_spinlock_t plock;

class CStyleAllocPrinter : public MatchFinder::MatchCallback
{
public:
  CStyleAllocPrinter(std::map<std::string, tooling::Replacements> &Replacements) : Replacements(Replacements) {}

  virtual void run(const MatchFinder::MatchResult &Result)
  {
    //ASTContext* context = Result.Context;

    // const CallExpr* callex = Result.Nodes.getNodeAs<CallExpr>("callex");
    const ExplicitCastExpr *castex = Result.Nodes.getNodeAs<ExplicitCastExpr>("castex");
    const clang::CallExpr *mnode = Result.Nodes.getNodeAs<clang::CallExpr>("malloc");

    // SourceLocation s = mnode->getBeginLoc();
    Replacement Rep(*(Result.SourceManager), mnode->getBeginLoc().getLocWithOffset(MTDFLEN), 0, "<" + castex->getTypeInfoAsWritten()->getType().getAsString() + ">");
    auto err = Replacements[Rep.getFilePath().str()].add(Rep);

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
  std::map<std::string, tooling::Replacements> &Replacements;
};

class sizeofMallocPrinter : public MatchFinder::MatchCallback
{
public:
  sizeofMallocPrinter(Rewriter &rewriter): rewriter(rewriter) {}

  virtual void run(const MatchFinder::MatchResult &Result)
  {
    const clang::CallExpr *mnode = Result.Nodes.getNodeAs<clang::CallExpr>("sizeofmalloc");
    const clang::Type *typenode = Result.Nodes.getNodeAs<clang::Type>("sizeof-arg-type");

    std::string type;

    static PrintingPolicy print_policy((Result.Context)->getLangOpts());
    print_policy.FullyQualifiedName = 1;
    print_policy.SuppressScope = 0;

    if (typenode->isBuiltinType())
    {
      type = typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy);
    }
    else if (typenode->isRecordType())
    {
      type = typenode->getAsRecordDecl()->getQualifiedNameAsString();
    }
    else if (typenode->isPointerType())
    {
      type = typenode->getPointeeType().getAsString();
    }

    // Replacement Rep(*(Result.SourceManager), mnode->getExprLoc().getLocWithOffset(MTDFLEN), 0, "<" + type + ">");
    // if (replSet.find({Rep.getFilePath().str(), mnode->getExprLoc().getLocWithOffset(MTDFLEN)}) == replSet.end())
    // {
    //   pthread_spin_lock(&plock);
    //   replSet.insert({Rep.getFilePath().str(), mnode->getExprLoc().getLocWithOffset(MTDFLEN)});
    //   pthread_spin_unlock(&plock);
    //   if (auto err = Replacements[Rep.getFilePath().str()].add(Rep))
    //   {
    //     cout << "replacements error" << endl;
    //   }
    // }
    rewriter.InsertText(mnode->getExprLoc().getLocWithOffset(MTDFLEN), "<" + type + ">", false, false);
  }

private:
  // std::map<std::string, tooling::Replacements> &Replacements;
  Rewriter &rewriter;
};

//Handler for lhs of malloc expressions
class lhsofMallocPrinter : public MatchFinder::MatchCallback
{
public:
  lhsofMallocPrinter(std::map<std::string, tooling::Replacements> &Replacements) : Replacements(Replacements) {}

  virtual void run(const MatchFinder::MatchResult &Result)
  {
    const clang::CallExpr *mnode = Result.Nodes.getNodeAs<clang::CallExpr>("lhsmalloc");
    const clang::Type *typenode = Result.Nodes.getNodeAs<clang::Type>("lhs-type");

    std::string type;

    static PrintingPolicy print_policy((Result.Context)->getLangOpts());
    print_policy.FullyQualifiedName = 1;
    print_policy.SuppressScope = 0;

    if (typenode->isBuiltinType())
    {
      type = typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy);
    }
    else if (typenode->isRecordType())
    {
      type = typenode->getAsRecordDecl()->getQualifiedNameAsString();
    }
    else if (typenode->isPointerType())
    {
      type = typenode->getPointeeType().getAsString();
    }

    Replacement Rep(*(Result.SourceManager), mnode->getBeginLoc().getLocWithOffset(MTDFLEN), 0, "<" + type + ">");
    auto err = Replacements[Rep.getFilePath().str()].add(Rep);
  }

private:
  std::map<std::string, tooling::Replacements> &Replacements;
};

class declMallocPrinter : public MatchFinder::MatchCallback
{
public:
  declMallocPrinter(std::map<std::string, tooling::Replacements> &Replacements) : Replacements(Replacements) {}

  virtual void run(const MatchFinder::MatchResult &Result)
  {
    const clang::CallExpr *mnode = Result.Nodes.getNodeAs<clang::CallExpr>("declmalloc");
    const clang::Type *typenode = Result.Nodes.getNodeAs<clang::Type>("decltype");

    std::string type;

    static PrintingPolicy print_policy((Result.Context)->getLangOpts());
    print_policy.FullyQualifiedName = 1;
    print_policy.SuppressScope = 0;

    if (typenode->isBuiltinType())
    {
      type = typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy);
    }
    else if (typenode->isRecordType())
    {
      type = typenode->getAsRecordDecl()->getQualifiedNameAsString();
    }
    else if (typenode->isPointerType())
    {
      type = typenode->getPointeeType().getAsString();
    }

    Replacement Rep(*(Result.SourceManager), mnode->getBeginLoc().getLocWithOffset(MTDFLEN), 0, "<" + type + ">");
    auto err = Replacements[Rep.getFilePath().str()].add(Rep);
  }

private:
  std::map<std::string, tooling::Replacements> &Replacements;
};

void copyFile(const std::string &src, const std::string &dst)
{
  std::ifstream source(src, std::ios::binary);
  std::ofstream dest(dst, std::ios::binary);
  dest << source.rdbuf();
}

class MyASTConsumer : public ASTConsumer {
public:
  MyASTConsumer(Rewriter &R) : sizeofMallocHandler(R) {
    Matcher.addMatcher(sizeofMallocMatcher, &sizeofMallocHandler);

  }
  void HandleTranslationUnit(ASTContext &Context) override {
    // Run the matchers when we have the whole TU parsed.
    Matcher.matchAST(Context);
  }

private:
  // CStyleAllocPrinter CStyleMallocHandler(Tool.getReplacements());
  sizeofMallocPrinter sizeofMallocHandler;
  // lhsofMallocPrinter lhsofMallocHandler(Tool.getReplacements());
  // declMallocPrinter declMallocHandler(Tool.getReplacements());
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

int main(int argc, const char **argv)
{
  std::string errorMsg;

  unique_ptr<CompilationDatabase> compDatabase = CompilationDatabase::autoDetectFromDirectory(argv[1], errorMsg);

  // IntrusiveRefCntPtr<DiagnosticOptions> DiagOpts = new DiagnosticOptions();
  //   DiagnosticsEngine Diagnostics(
  //       IntrusiveRefCntPtr<DiagnosticIDs>(new DiagnosticIDs()), &*DiagOpts,
  //       new TextDiagnosticPrinter(llvm::errs(), &*DiagOpts), true);

  RefactoringTool Tool(*compDatabase.get(), compDatabase->getAllFiles());

  // SourceManager Sources(Diagnostics, Tool.getFiles());
  
  MatchFinder Finder;

  // rewriter.setSourceMgr(Sources, );

  // Finder.addMatcher(CStyleMallocMatcher, &CStyleMallocHandler);
  // Finder.addMatcher(sizeofMallocMatcher, &sizeofMallocHandler);
  // Finder.addMatcher(lhsofMallocMatcher, &lhsofMallocHandler);
  // Finder.addMatcher(declMallocMatcher, &declMallocHandler);

  if (int Result = Tool.run(newFrontendActionFactory<MyFrontendAction>().get()))
  {
    return Result;
  }

  // llvm::outs() << "Replacements collected by the tool:\n";
  // for (auto &R : Tool.getReplacements())
  // {
  //   cout << R.first;
  //   for (auto &i : R.second)
  //   {
  //     llvm::outs() << i.toString() << "\n";
  //   }
  // }

  return 0;
}