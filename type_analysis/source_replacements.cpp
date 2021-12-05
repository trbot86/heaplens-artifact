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
#include <clang/Tooling/CommonOptionsParser.h>
//
#include <clang/Tooling/JSONCompilationDatabase.h>
//
#include <clang/Tooling/Refactoring.h>
#include <clang/Tooling/Core/Replacement.h>
#include <clang/Tooling/Tooling.h>
#include <llvm/Support/raw_ostream.h>

using namespace clang;
using namespace clang::ast_matchers;
using namespace clang::driver;
using namespace clang::tooling;

static llvm::cl::OptionCategory ToolingSampleCategory("Tooling Sample");

StatementMatcher CStyleMallocMatcher =
    // declRefExpr(hasDeclaration(functionDecl(hasName("malloc"))))
    // explicitCastExpr(isExpansionInMainFile(), hasDescendant(callExpr(callee(functionDecl(anyOf(hasName("malloc"), hasName("realloc"), hasName("calloc"), hasName("reallocArray"))))).bind("callex"))).bind("castex");
    explicitCastExpr(hasDescendant(declRefExpr(hasDeclaration(functionDecl(hasName("malloc")))).bind("malloc"))).bind("castex");

class IfStmtHandler : public MatchFinder::MatchCallback
{
public:
  IfStmtHandler(Replacements *Replace) : Replace(Replace) {}

  virtual void run(const MatchFinder::MatchResult &Result)
  {
    std::cout << "in the callback" << std::endl;
    // The matched 'if' statement was bound to 'ifStmt'.
    if (const IfStmt *IfS = Result.Nodes.getNodeAs<clang::IfStmt>("ifStmt"))
    {
      const Stmt *Then = IfS->getThen();
      Replacement Rep(*(Result.SourceManager), Then->getBeginLoc(), 0,
                      "// the 'if' part\n");
      Replace->add(Rep);

      if (const Stmt *Else = IfS->getElse())
      {
        Replacement Rep(*(Result.SourceManager), Else->getEndLoc(), 0,
                        "// the 'else' part\n");
        Replace->add(Rep);
      }
    }
  }

private:
  Replacements *Replace;
};

class CStyleAllocPrinter : public MatchFinder::MatchCallback {
  public:
    CStyleAllocPrinter(Replacements *Replace) : Replace(Replace) {}

    virtual void run(const MatchFinder::MatchResult &Result) {
      //ASTContext* context = Result.Context;

      // const CallExpr* callex = Result.Nodes.getNodeAs<CallExpr>("callex");
      const ExplicitCastExpr* castex = Result.Nodes.getNodeAs<ExplicitCastExpr>("castex");
      const DeclRefExpr* mnode = Result.Nodes.getNodeAs<DeclRefExpr>("malloc");

      Replacement Rep(*(Result.SourceManager), mnode->getBeginLoc(), 0, "<" + castex->getTypeInfoAsWritten()->getType().getAsString() + ">");
      Replace->add(Rep);

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
    Replacements *Replace;
};

void copyFile(const std::string &src, const std::string &dst)
{
  std::ifstream source(src, std::ios::binary);
  std::ofstream dest(dst, std::ios::binary);
  dest << source.rdbuf();
}

int main(int argc, const char **argv)
{
  std::string errorMsg;
  auto compDatabase = JSONCompilationDatabase::loadFromFile(argv[1], errorMsg, JSONCommandLineSyntax::AutoDetect);

  //CommonOptionsParser op(argc, argv, ToolingSampleCategory, llvm::cl::OneOrMore);

  // for (auto s : compDatabase->getAllFiles())
  // {
  //   std::cout << s << std::endl;
  // }

  std::vector<std::string> fileSources = compDatabase->getAllFiles();

  for (const auto &src : fileSources)
  {
    std::string tmpFile = src + ".tmp";
    copyFile(src, tmpFile);

    RefactoringTool Tool(*compDatabase.get(), src);
    MatchFinder Finder;

    Replacements *replacementsToUse;
    replacementsToUse = &(Tool.getReplacements()[src]);

    // Set up AST matcher callbacks.
    // IfStmtHandler HandlerForIf(replacementsToUse);
    // Finder.addMatcher(ifStmt(unless(isExpansionInSystemHeader())).bind("ifStmt"), &HandlerForIf);

    CStyleAllocPrinter HandlerForAllocs(replacementsToUse);
    Finder.addMatcher(CStyleMallocMatcher, &HandlerForAllocs);

    // Run the tool and collect a list of replacements. We could call runAndSave,
    // which would destructively overwrite the files with their new contents.
    // However, for demonstration purposes it's interesting to print out the
    // would-be contents of the rewritten files instead of actually rewriting
    // them.
    if (int Result = Tool.run(newFrontendActionFactory(&Finder).get()))
    {
      return Result;
    }

    llvm::outs() << "Replacements collected by the tool:\n";
    for (auto &r : Tool.getReplacements()[src])
    {
      llvm::outs() << r.toString() << "\n";
    }

    // // We need a SourceManager to set up the Rewriter.
    // IntrusiveRefCntPtr<DiagnosticOptions> DiagOpts = new DiagnosticOptions();
    // DiagnosticsEngine Diagnostics(
    //     IntrusiveRefCntPtr<DiagnosticIDs>(new DiagnosticIDs()), &*DiagOpts,
    //     new TextDiagnosticPrinter(llvm::errs(), &*DiagOpts), true);
    // SourceManager Sources(Diagnostics, Tool.getFiles());

    // // Apply all replacements to a rewriter.
    // Rewriter Rewrite(Sources, LangOptions());
    // Tool.applyAllReplacements(Rewrite);

    // // Query the rewriter for all the files it has rewritten, dumping their new
    // // contents to stdout.
    // for (Rewriter::buffer_iterator I = Rewrite.buffer_begin(),
    //                                E = Rewrite.buffer_end();
    //      I != E; ++I)
    // {
    //   const FileEntry *Entry = Sources.getFileEntryForID(I->first);
    //   llvm::outs() << "Rewrite buffer for file: " << Entry->getName() << "\n";
    //   I->second.write(llvm::outs());
    // }
  }

  return 0;
}