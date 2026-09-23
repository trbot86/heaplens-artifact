//===--- AllocationLoggingCheck.cpp - clang-tidy --------------------------===//
//
// Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
//
//===----------------------------------------------------------------------===//

#include "AllocationLoggingCheck.h"
#include "clang/AST/ASTContext.h"
#include "clang/ASTMatchers/ASTMatchFinder.h"
#include "clang/ASTMatchers/ASTMatchers.h"

#include <iostream>

#define MATCH_FUNCTIONS allOf(anyOf(hasName("_mm_malloc"), \
                                    hasName("alloc"), \
                                    hasName("malloc"), \
                                    hasName("ssmem_alloc"), \
                                    hasName("ssalloc"), \
                                    hasName("memalign"), \
                                    hasName("posix_memalign"), \
                                    hasName("calloc"), \
                                    hasName("xmalloc"), \
                                    hasName("xcalloc"), \
                                    hasName("Allocate"), \
                                    hasName("AllocateAligned")), unless(isTemplateInstantiation()))

using namespace clang::ast_matchers;

StatementMatcher sizeofMallocMatcher = expr(sizeOfExpr(allOf(
    hasAncestor(
        callExpr(hasDescendant(
            declRefExpr(to((functionDecl(MATCH_FUNCTIONS)))).bind("sizeofmalloc")
        ))
    ),
    hasArgumentOfType(
        hasUnqualifiedDesugaredType(type().bind("sizeof-arg-type"))))));

// StatementMatcher sizeofMallocMatcher = 
//     sizeOfExpr(
//         hasAncestor(
//             callExpr(hasDescendant(
//                 declRefExpr(to((functionDecl(MATCH_FUNCTIONS)))).bind("sizeofmalloc")
//             ))
//         )
//     ).bind("sizeofexpr");

// matches malloc lhs without explicit casts
StatementMatcher lhsofMallocMatcher = binaryOperator(
    hasOperatorName("="),
    anyOf(hasDescendant(callExpr(callee(functionDecl(MATCH_FUNCTIONS).bind("fdecllhsmalloc")))
                            .bind("lhsmalloc")),
        hasRHS(hasDescendant(callExpr(callee(functionDecl(MATCH_FUNCTIONS)))
                                   .bind("lhsmalloc")))),
    hasLHS(hasType(type().bind("lhs-type"))));

DeclarationMatcher declMallocMatcher = varDecl(
    hasDescendant(
        callExpr(callee(functionDecl(MATCH_FUNCTIONS).bind("fdeclmalloc"))).bind("declmalloc")),
    hasType(type().bind("decltype")));

StatementMatcher returnMallocMatcher = returnStmt(
    hasDescendant(callExpr(callee(functionDecl(MATCH_FUNCTIONS).bind("fretmalloc"))).bind("retmalloc")), 
    hasReturnValue(hasType(type().bind("rettype"))));

// // Matches declaration with placement new allocation
// DeclarationMatcher placementNewDeclMatcher = varDecl(hasDescendant(
//         cxxNewExpr(hasAnyPlacementArg(anything())).bind("pnewExpr")
//     ),
//     hasType(type().bind("pnew-decl-type")));

// // Matches assignment with placement new allocation
// StatementMatcher placementNewAssignMatcher = binaryOperator(
//     hasOperatorName("="),
//     hasRHS(hasDescendant(cxxNewExpr(hasAnyPlacementArg(anything()))))
// ).bind("assign-op");

// Matches allocation with new
StatementMatcher newMatcher = cxxNewExpr().bind("new-expr");

namespace clang {
namespace tidy {
namespace misc {

// AllocationLoggingCheck::AllocationLoggingCheck(StringRef Name, ClangTidyContext *Context)
//       : TransformerClangTidyCheck(Name, Context) {
//   setRule(
//     clang::transformer::applyFirst({
// #ifdef ALLOCLOGGING_TEMPLATE
//       clang::transformer::makeRule(sizeofMallocMatcher, // TODO should this actually be after NAME of node, not node itself?
//                clang::transformer::insertAfter(clang::transformer::node("sizeofmalloc"), clang::transformer::cat("<", clang::transformer::node("sizeofexpr"), ", __LINE__, __FILE__>")),
//                clang::transformer::cat("sizeof malloc: Insert line number, file name, and type."))
//     //   clang::transformer::makeRule(lhsofMallocMatcher,
//     //            clang::transformer::changeTo(clang::transformer::after(clang::transformer::node("lhsmalloc")), clang::transformer::cat("<", clang::transformer::node("lhs-type"), ", __LINE__, __FILE__>")),
//     //            clang::transformer::cat("LHS malloc: Insert line number, file name, and type.")),
//     //   clang::transformer::makeRule(declMallocMatcher,
//     //            clang::transformer::changeTo(clang::transformer::after(clang::transformer::node("fdeclmalloc")), clang::transformer::cat("<", clang::transformer::node("decltype"), ", __LINE__, __FILE__>")),
//     //            clang::transformer::cat("Declaration malloc: Insert line number, file name, and type.")),
//     //   clang::transformer::makeRule(placementNewDeclMatcher,
//     //            clang::transformer::changeTo(clang::transformer::before(clang::transformer::node("pnewExpr")), clang::transformer::cat("MemStamp((__FILE__), (__LINE__)) * (", clang::transformer::node("pnew-decl-type"), ") ")),
//     //            clang::transformer::cat("Placement new declaration: Insert line number, file name, and type.")),
//     //   clang::transformer::makeRule(placementNewAssignMatcher,
//     //            clang::transformer::changeTo(clang::transformer::after(clang::transformer::node("assign-op")), clang::transformer::cat("MemStamp((__FILE__), (__LINE__)) *")),
//     //            clang::transformer::cat("Placement new assignment: Insert line number and file name.")),
//     //   clang::transformer::makeRule(newMatcher,
//     //            clang::transformer::insertBefore(clang::transformer::node("new-expr"), clang::transformer::cat("MemStamp((__FILE__), (__LINE__)) * ")),
//     //            clang::transformer::cat("new: Insert line number and file name."))
// #else
//       clang::transformer::makeRule(sizeofMallocMatcher,
//                {clang::transformer::changeTo(clang::transformer::after(clang::transformer::node("sizeofmalloc")), clang::transformer::cat("_s")),
//                 clang::transformer::changeTo(clang::transformer::after(clang::transformer::callArgs("sizeofmalloc")), clang::transformer::cat(", __LINE__, __FILE__, ", clang::transformer::node("sizeof-arg-type")))},
//                clang::transformer::cat("sizeof malloc: Insert line number, file name, and type.")),
//       clang::transformer::makeRule(lhsofMallocMatcher,
//                {clang::transformer::changeTo(clang::transformer::after(clang::transformer::node("lhsmalloc")), clang::transformer::cat("_s")),
//                 clang::transformer::changeTo(clang::transformer::after(clang::transformer::callArgs("lhsmalloc")), clang::transformer::cat(", __LINE__, __FILE__, ", clang::transformer::node("lhs-type")))},
//                clang::transformer::cat("LHS malloc: Insert line number, file name, and type.")),
//       clang::transformer::makeRule(declMallocMatcher,
//                {clang::transformer::changeTo(clang::transformer::after(clang::transformer::node("fdeclmalloc")), clang::transformer::cat("_s")),
//                 clang::transformer::changeTo(clang::transformer::after(clang::transformer::callArgs("fdeclmalloc")), clang::transformer::cat(", __LINE__, __FILE__, ", clang::transformer::node("decltype")))},
//                clang::transformer::cat("Declaration malloc: Insert line number, file name, and type."))
// #endif
//     }) // applyFirst
//   ); // setRule
// }

void AllocationLoggingCheck::registerMatchers(MatchFinder *Finder) {
    Finder->addMatcher(sizeofMallocMatcher, this);
    Finder->addMatcher(lhsofMallocMatcher, this);
    Finder->addMatcher(declMallocMatcher, this);
    //Finder->addMatcher(returnMallocMatcher, this);
#ifdef ALLOCLOGGING_TEMPLATE
    Finder->addMatcher(newMatcher, this);
#endif
}

void AllocationLoggingCheck::emitDiagnosticsMalloc(const MatchFinder::MatchResult &Result, std::string allocnodebind, std::string typenodebind, std::string declnodebind) {
    const clang::CallExpr *mnode =
        Result.Nodes.getNodeAs<clang::CallExpr>(allocnodebind);
    const clang::FunctionDecl *declnode =
        Result.Nodes.getNodeAs<clang::FunctionDecl>(declnodebind);
    const clang::Type *typenode =
        Result.Nodes.getNodeAs<clang::Type>(typenodebind);

    if(mnode) {
        if(declnode) {
            std::string type;

            static PrintingPolicy print_policy((Result.Context)->getLangOpts());
            print_policy.FullyQualifiedName = 0;
            print_policy.SuppressScope = 1;

            if (typenode->isBuiltinType()) {
                type = typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy);
            }
            else if (typenode->isRecordType()) {
                type = typenode->getAsRecordDecl()->getQualifiedNameAsString();
            }
            else if (typenode->isPointerType()) {
                type = typenode->getPointeeType().getAsString();
            }
#ifndef ALLOCLOGGING_TEMPLATE
            if (typemap.find(type) == typemap.end()) {
                typemap[type] = typemap.size();
            }
#endif

            FullSourceLoc fsrcloc = Result.Context->getFullLoc(mnode->getExprLoc());
            /* TODO: get the following to work will allocations performed in macro defs */
            if (!fsrcloc.isMacroID()) {
                std::string FileName = fsrcloc.getFileEntry()->getName().str();
                if (filemap.find(FileName) == filemap.end()) {
                    filemap[FileName] = filemap.size();
                }
                int line = fsrcloc.getLineNumber();

                // SmallString<200> pathVector;
                //   std::cout << "FILENAME: "
                //             << pathVector.c_str() + fsrcloc.getFileEntry()->getName().str()
                //             << ": " << line << endl;

                // std::cout << "DeclName: " << declnode->getNameAsString() << endl;
                int offset = declnode->getNameAsString().size();

    #ifdef ALLOCLOGGING_TEMPLATE
                diag(mnode->getExprLoc().getLocWithOffset(offset), "insert type here",
                    DiagnosticIDs::Warning)
                    << FixItHint::CreateInsertion(
                        mnode->getExprLoc().getLocWithOffset(offset),
                        "<" + type + ", " + std::to_string(line) + ", " + std::to_string(filemap[FileName]) + ">");
    #else    
                diag(mnode->getExprLoc().getLocWithOffset(offset), "insert _s here",
                    DiagnosticIDs::Warning)
                    << FixItHint::CreateInsertion(
                        mnode->getExprLoc().getLocWithOffset(offset), "_s");
                diag(mnode->getEndLoc(), "insert file name, line number, and type",
                    DiagnosticIDs::Warning)
                    << FixItHint::CreateInsertion(
                        mnode->getEndLoc(),
                        ", " + std::to_string(line) + ", " + std::to_string(filemap[FileName]) + ", " + std::to_string(typemap[type]));
    #endif // TEMPLATE
            }
        }
    }
}

void AllocationLoggingCheck::emitDiagnosticsNew(const MatchFinder::MatchResult &Result, std::string newbind) {
    const clang::CXXNewExpr* node =
        Result.Nodes.getNodeAs<clang::CXXNewExpr>(newbind);

    if (node) {
        auto &SM = Result.Context->getSourceManager();
        std::string FileName = SM.getFilename(node->getExprLoc()).str();
        if (filemap.find(FileName) == filemap.end()) {
            filemap[FileName] = filemap.size();
        }
        if (node->getNumPlacementArgs() == 0) {
            diag(node->getExprLoc(), "insert MemStamp",
                DiagnosticIDs::Warning)
                << FixItHint::CreateInsertion(
                        node->getExprLoc(),
                        "MemStamp(" + std::to_string(filemap[FileName]) + ", (__LINE__)) * ");
        }
#ifdef ALLOCLOGGING_PLACEMENT_NEW
        // TODO: if dereference on same line, need to put parentheses around like *(MemStamp() * (T*) new () T())
        else if (node->getNumPlacementArgs() > 0) {
            std::string type = node->getAllocatedType().getUnqualifiedType().getAsString();
            // std::string type = node->getAllocatedType().getTypePtr()->getAs<clang::RecordType>()->getDecl()->getNameAsString();
            std::string out = "MemStamp(" + std::to_string(filemap[FileName]) + ", (__LINE__)) * (" + type + "*) ";
            diag(node->getExprLoc(), "insert MemStamp (placement new)",
                DiagnosticIDs::Warning)
                << FixItHint::CreateInsertion(
                        node->getExprLoc(),
                        out);
        }
#endif
    }
}

void AllocationLoggingCheck::check(const MatchFinder::MatchResult &Result) {
    // FIXME: Add callback implementation.
    // std::cout << "CHECK\n" << std::endl;

    AllocationLoggingCheck::emitDiagnosticsMalloc(Result, "sizeofmalloc", "sizeof-arg-type", "fdeclsizeofmalloc");
    AllocationLoggingCheck::emitDiagnosticsMalloc(Result, "lhsmalloc", "lhs-type", "fdecllhsmalloc");
    AllocationLoggingCheck::emitDiagnosticsMalloc(Result, "declmalloc", "decltype", "fdeclmalloc");
    //AllocationLoggingCheck::emitDiagnosticsMalloc(Result, "retmalloc", "rettype", "fretmalloc");

#ifdef ALLOCLOGGING_TEMPLATE
    AllocationLoggingCheck::emitDiagnosticsNew(Result, "new-expr");
#endif
}

} // namespace misc
} // namespace tidy
} // namespace clang
