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
#include <llvm/Support/CommandLine.h>

#define MAX_FILE_PATH 200

using namespace clang;
using namespace clang::ast_matchers;
using namespace clang::driver;
using namespace clang::tooling;

using namespace std;

static llvm::cl::OptionCategory ToolingSampleCategory("Tooling Sample");
static llvm::cl::extrahelp CommonHelp(CommonOptionsParser::HelpMessage);

StatementMatcher sizeofMallocMatcher =
    expr(sizeOfExpr(allOf(hasAncestor(callExpr(callee(functionDecl(hasName(MTDFNAME)))).bind("sizeofmalloc")),
                          hasArgumentOfType(hasUnqualifiedDesugaredType(type().bind("sizeof-arg-type"))))));

class sizeofMallocPrinter : public MatchFinder::MatchCallback
{
private:
    std::map<std::string, tooling::Replacements> &replacements;

public:
    sizeofMallocPrinter(std::map<std::string, tooling::Replacements> &replacements) : replacements(replacements) {}

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

        FullSourceLoc fsrcloc = Result.Context->getFullLoc(mnode->getExprLoc());
        string FileName = fsrcloc.getFileEntry()->getName().str();
        int line = fsrcloc.getLineNumber();

        SmallString<MAX_FILE_PATH> pathVector;
        std::cout << "FILENAME: " << pathVector.c_str() + fsrcloc.getFileEntry()->getName().str() << ": " << line << endl;
        Replacement Rep(*(Result.SourceManager), mnode->getExprLoc().getLocWithOffset(MTDFLEN), 0, std::string(MTDFNAME) + "<" + type + ", MACRO_GET_STR(\"" + FileName + "\"), " + to_string(line) + ">");

        cout << Rep.getFilePath().str() << endl;

        // if (auto error = replacements[Rep.getFilePath().str()].add(Rep))
        // {
        //     llvm::outs() << "ERROR" << error;
        // }
        // replacements[Rep.getFilePath().str()] = replacements[Rep.getFilePath().str()].merge(tooling::Replacements(Rep));
        llvm::consumeError(replacements[Rep.getFilePath().str()].add(Rep));
    }
};

Replacements &getReplacements(RefactoringTool &Tool, StringRef file)
{
    // getReplacements() now returns a map from filename to Replacements - so create an entry
    // for this source file and return a reference to it.
    return Tool.getReplacements()[std::string(file)];
}

int main(int argc, const char **argv)
{
    cout << LLVM_VERSION_MAJOR << " " << LLVM_VERSION_MINOR << endl;
    std::string errorMsg;
    CommonOptionsParser OptionsParser(argc, argv, ToolingSampleCategory);

    unique_ptr<CompilationDatabase> compDatabase = CompilationDatabase::autoDetectFromDirectory(argv[1], errorMsg);

    std::vector<std::string> fileSources = compDatabase->getAllFiles();

    Replacements gRep;
    RefactoringTool Tool(*compDatabase.get(), fileSources);

    sizeofMallocPrinter sizeofMallocHandler(Tool.getReplacements());
    MatchFinder Finder;
    Finder.addMatcher(sizeofMallocMatcher, &sizeofMallocHandler);
    if (int result = Tool.run(newFrontendActionFactory(&Finder).get()))
    {
        return -1;
    }

    // We need a SourceManager to set up the Rewriter.
    IntrusiveRefCntPtr<DiagnosticOptions> DiagOpts = new DiagnosticOptions();
    DiagnosticsEngine Diagnostics(
        IntrusiveRefCntPtr<DiagnosticIDs>(new DiagnosticIDs()), &*DiagOpts,
        new TextDiagnosticPrinter(llvm::errs(), &*DiagOpts), true);
    SourceManager Sources(Diagnostics, Tool.getFiles());

    // Apply all replacements to a rewriter.
    Rewriter Rewrite(Sources, LangOptions());
    // Tool.applyAllReplacements(Rewrite);
    // Rewrite.overwriteChangedFiles();

    // Query the rewriter for all the files it has rewritten, dumping their new
    // contents to stdout.
    for (Rewriter::buffer_iterator I = Rewrite.buffer_begin(),
                                   E = Rewrite.buffer_end();
         I != E; ++I)
    {
        const FileEntry *Entry = Sources.getFileEntryForID(I->first);
        llvm::outs() << "Rewrite buffer for file: " << Entry->getName() << "\n";
        I->second.write(llvm::outs());
    }
    llvm::outs() << "Replacements collected by the tool:\n";
    for (auto &R : Tool.getReplacements())
    {
        cout << R.first << endl;
        for (auto &i : R.second)
        {
            llvm::outs() << i.toString() << "\n";
        }
    }

    return 0;
}
