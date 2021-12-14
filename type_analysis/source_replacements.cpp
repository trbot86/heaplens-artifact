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
// #include <clang/Tooling/Core/Replacement.h>
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

class CStyleAllocPrinter : public MatchFinder::MatchCallback
{
public:
  CStyleAllocPrinter(Replacements *Replace) : Replace(Replace) {}

  virtual void run(const MatchFinder::MatchResult &Result)
  {
    //ASTContext* context = Result.Context;

    // const CallExpr* callex = Result.Nodes.getNodeAs<CallExpr>("callex");
    const ExplicitCastExpr *castex = Result.Nodes.getNodeAs<ExplicitCastExpr>("castex");
    const clang::CallExpr* mnode = Result.Nodes.getNodeAs<clang::CallExpr>("malloc");

    // SourceLocation s = mnode->getBeginLoc();
    Replacement Rep(*(Result.SourceManager), mnode->getBeginLoc(), 5, "<" + castex->getTypeInfoAsWritten()->getType().getAsString() + ">");
    // auto err = Replace->add(Rep);

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

class sizeOfMallocPrinter : public MatchFinder::MatchCallback {
  public:
  sizeOfMallocPrinter(Replacements *Replace) : Replace(Replace) {}

  virtual void run(const MatchFinder::MatchResult &Result) {
    const clang::CallExpr* mnode = Result.Nodes.getNodeAs<clang::CallExpr>("sizeofmalloc");
    const clang::Type* typenode = Result.Nodes.getNodeAs<clang::Type>("sizeof-arg-type");

    std::string type;

    static PrintingPolicy print_policy((Result.Context)->getLangOpts());
    print_policy.FullyQualifiedName = 1;
    print_policy.SuppressScope = 0;

    if(typenode->isBuiltinType()) {
      type = typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy);
    }
    else if(typenode->isRecordType()) {
      type = typenode->getAsRecordDecl()->getQualifiedNameAsString();
    }
    else if(typenode->isPointerType()) {
      type = typenode->getPointeeType().getAsString();
    }

    Replacement Rep(*(Result.SourceManager), mnode->getBeginLoc(), 0, "<" + type + ">");
    auto err = Replace->add(Rep);
  }

  private:
  Replacements *Replace;
};

//Handler for lhs of malloc expressions
class lhsOfMallocPrinter : public MatchFinder::MatchCallback {
  public:

  virtual void run(const MatchFinder::MatchResult &Result) {
    const clang::CallExpr* mnode = Result.Nodes.getNodeAs<clang::CallExpr>("lhsmalloc");
    const clang::Type* typenode = Result.Nodes.getNodeAs<clang::Type>("lhs-type");

    std::string type;

    static PrintingPolicy print_policy((Result.Context)->getLangOpts());
    print_policy.FullyQualifiedName = 1;
    print_policy.SuppressScope = 0;

    if(typenode->isBuiltinType()) {
      type = typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy);
    }
    else if(typenode->isRecordType()) {
      type = typenode->getAsRecordDecl()->getQualifiedNameAsString();
    }
    else if(typenode->isPointerType()) {
      type = typenode->getPointeeType().getAsString();
    }

    Replacement Rep(*(Result.SourceManager), mnode->getBeginLoc(), 0, "<" + type + ">");
    auto err = Replace->add(Rep);
  }

  private:
  Replacements *Replace;
};

class declMallocPrinter : public MatchFinder::MatchCallback {
  public:

  virtual void run(const MatchFinder::MatchResult &Result) {
    const clang::CallExpr* mnode = Result.Nodes.getNodeAs<clang::CallExpr>("declmalloc");
    const clang::Type* typenode = Result.Nodes.getNodeAs<clang::Type>("decltype");

    std::string type;

    static PrintingPolicy print_policy((Result.Context)->getLangOpts());
    print_policy.FullyQualifiedName = 1;
    print_policy.SuppressScope = 0;

    if(typenode->isBuiltinType()) {
      type = typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy);
    }
    else if(typenode->isRecordType()) {
      type = typenode->getAsRecordDecl()->getQualifiedNameAsString();
    }
    else if(typenode->isPointerType()) {
      type = typenode->getPointeeType().getAsString();
    }

    Replacement Rep(*(Result.SourceManager), mnode->getBeginLoc(), 0, "<" + type + ">");
    auto err = Replace->add(Rep);
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
    sizeOfMallocPrinter sizeOfMallocHandler(replacementsToUse);
    // Finder.addMatcher(CStyleMallocMatcher, &HandlerForAllocs);
    Finder.addMatcher(sizeofMallocMatcher, &HandlerForAllocs);
    Finder.addMatcher(lhsofMallocMatcher, &HandlerForAllocs);
    Finder.addMatcher(declMallocMatcher, &HandlerForAllocs);

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

  }

  return 0;
}