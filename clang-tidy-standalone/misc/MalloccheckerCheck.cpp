#include "memhook_interface.h"
// #define MALLOCCHECKER_NOTEMPLATE
//===--- MalloccheckerCheck.cpp - clang-tidy ------------------------------===//
//
// Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
//
//===----------------------------------------------------------------------===//

#include "MalloccheckerCheck.h"
#include "clang/AST/ASTContext.h"
#include "clang/ASTMatchers/ASTMatchFinder.h"
#include "clang/ASTMatchers/ASTMatchers.h"

#include <iostream>

#define MTDFNAME "_mm_malloc"
#define MTDFNAME2 "alloc"
#define MTDFNAME3 "malloc"
#define MTDFNAME4 "ssmem_alloc"
#define MTDFNAME5 "ssalloc"
#define MTDFNAME6 "memalign"
#define MTDFNAME7 "posix_memalign"
#define MATCH_FUNCTIONS allOf(anyOf(hasName(MTDFNAME),
                                    hasName(MTDFNAME2),
                                    hasName(MTDFNAME3),
                                    hasName(MTDFNAME4),
                                    hasName(MTDFNAME5),
                                    hasName(MTDFNAME6),
                                    hasName(MTDFNAME7)), unless(isTemplateInstantiation()))
// #define MATCH_FUNCTIONS hasName(MTDFNAME)

using namespace clang::ast_matchers;
using namespace std;



StatementMatcher sizeofMallocMatcher = expr(sizeOfExpr(allOf(
    hasAncestor(
        callExpr(callee(functionDecl(MATCH_FUNCTIONS).bind("fdeclsizeofmalloc"))).bind("sizeofmalloc")),
    hasArgumentOfType(
        hasUnqualifiedDesugaredType(type().bind("sizeof-arg-type"))))));

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

namespace clang {
namespace tidy {
namespace misc {

void MalloccheckerCheck::registerMatchers(MatchFinder *Finder) {
  // FIXME: Add matchers.
  Finder->addMatcher(sizeofMallocMatcher, this);
  Finder->addMatcher(lhsofMallocMatcher, this);
  Finder->addMatcher(declMallocMatcher, this);
}

void MalloccheckerCheck::emitDiagnostics(const MatchFinder::MatchResult &Result, string allocnodebind, string typenodebind, string declnodebind) {
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
      print_policy.FullyQualifiedName = 1;
      print_policy.SuppressScope = 0;

      if (typenode->isBuiltinType()) {
        type =
            typenode->getAs<clang::BuiltinType>()->getNameAsCString(print_policy);
      } else if (typenode->isRecordType()) {
        type = typenode->getAsRecordDecl()->getQualifiedNameAsString();
      } else if (typenode->isPointerType()) {
        type = typenode->getPointeeType().getAsString();
      }

      FullSourceLoc fsrcloc = Result.Context->getFullLoc(mnode->getExprLoc());
      string FileName = fsrcloc.getFileEntry()->getName().str();
      int line = fsrcloc.getLineNumber();

      SmallString<200> pathVector;
        std::cout << "FILENAME: "
                  << pathVector.c_str() + fsrcloc.getFileEntry()->getName().str()
                  << ": " << line << endl;

      std::cout << "DeclName: " << declnode->getNameAsString() << endl;
      int offset = declnode->getNameAsString().size();

#ifdef MALLOCCHECKER_NOTEMPLATE
      diag(mnode->getExprLoc().getLocWithOffset(offset), "insert _s here",
          DiagnosticIDs::Error)
          << FixItHint::CreateInsertion(
                mnode->getExprLoc().getLocWithOffset(offset),
                "_s");
      diag(mnode->getEndLoc(), "insert file name, line number, and type",
          DiagnosticIDs::Error)
          << FixItHint::CreateInsertion(
                mnode->getEndLoc(),
                ", " + to_string(line) + ", \"" + FileName + "\", \"" + type + "\"");
#endif
#ifndef MALLOCCHECKER_NOTEMPLATE      
      diag(mnode->getExprLoc().getLocWithOffset(offset), "insert type here",
          DiagnosticIDs::Error)
          << FixItHint::CreateInsertion(
                mnode->getExprLoc().getLocWithOffset(offset),
                "<" + type + ", " + to_string(line) + ", MACRO_GET_STR(\"" + FileName + "\")" +
                      ">");
#endif // NOTEMPLATE
    }
  }
}

void MalloccheckerCheck::check(const MatchFinder::MatchResult &Result) {
  // FIXME: Add callback implementation.
  // std::cout << "CHECK\n" << std::endl;

  MalloccheckerCheck::emitDiagnostics(Result, "sizeofmalloc", "sizeof-arg-type", "fdeclsizeofmalloc");
  MalloccheckerCheck::emitDiagnostics(Result, "lhsmalloc", "lhs-type", "fdecllhsmalloc");
  MalloccheckerCheck::emitDiagnostics(Result, "declmalloc", "decltype", "fdeclmalloc");

}

} // namespace misc
} // namespace tidy
} // namespace clang
