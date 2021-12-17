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
    explicitCastExpr(hasDescendant(callExpr(callee(functionDecl(hasName(MTDFNAME)))).bind("malloc"))).bind("castex");

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
    Replacement Rep(*(Result.SourceManager), mnode->getBeginLoc(), 5, "<" + castex->getTypeInfoAsWritten()->getType().getAsString() + ">");
    cout << Rep.getFilePath().str() << endl;
    auto err = Replacements[Rep.getFilePath().str()].add(Rep);
  }

private:
  std::map<std::string, tooling::Replacements> &Replacements;
};

int main(int argc, const char **argv)
{
  std::string errorMsg;

  auto compDatabase = JSONCompilationDatabase::loadFromFile(argv[3], errorMsg, JSONCommandLineSyntax::AutoDetect);

  std::vector<std::string> fileSources = compDatabase->getAllFiles();

  for(auto i: fileSources) {
    cout << i << endl;
  }

  CommonOptionsParser Cp(argc, argv, ToolingSampleCategory);
  RefactoringTool Tool(compDatabase, Cp.getSourcePathList());
  MatchFinder Finder;

  CStyleAllocPrinter HandlerForAllocs(Tool.getReplacements());
  Finder.addMatcher(CStyleMallocMatcher, &HandlerForAllocs);

  if (int Result = Tool.run(newFrontendActionFactory(&Finder).get()))
  {
    return Result;
  }

  llvm::outs() << "Replacements collected by the tool:\n";
  for (auto& R: Tool.getReplacements()) {
    cout << R.first;
    for(auto& i: R.second) {
      llvm::outs() << i.toString() << "\n";
    }
  }

  return 0;
}