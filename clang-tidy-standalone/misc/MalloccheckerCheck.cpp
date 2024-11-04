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

#define MTDFNAME1 "_mm_malloc"
#define MTDFNAME2 "alloc"
#define MTDFNAME3 "malloc"
#define MTDFNAME4 "ssmem_alloc"
#define MTDFNAME5 "ssalloc"
#define MTDFNAME6 "memalign"
#define MTDFNAME7 "posix_memalign"
#define MTDFNAME8 "calloc"
#define MTDFNAME9 "xmalloc"
#define MTDFNAME10 "xcalloc"
#define MATCH_FUNCTIONS allOf(anyOf(hasName(MTDFNAME1), \
                                    hasName(MTDFNAME2), \
                                    hasName(MTDFNAME3), \
                                    hasName(MTDFNAME4), \
                                    hasName(MTDFNAME5), \
                                    hasName(MTDFNAME6), \
                                    hasName(MTDFNAME7), \
                                    hasName(MTDFNAME8), \
                                    hasName(MTDFNAME9), \
                                    hasName(MTDFNAME10)), unless(isTemplateInstantiation()))
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

// Matches allocation with new AND possibly placement new
StatementMatcher newMatcher = cxxNewExpr().bind("newExpr");


namespace clang {
namespace tidy {
namespace misc {

void MalloccheckerCheck::registerMatchers(MatchFinder *Finder) {
  // FIXME: Add matchers.
  Finder->addMatcher(sizeofMallocMatcher, this);
  Finder->addMatcher(lhsofMallocMatcher, this);
  Finder->addMatcher(declMallocMatcher, this);
#ifdef MALLOCCHECKER_TEMPLATE
  Finder->addMatcher(newMatcher, this);
#endif
}

void MalloccheckerCheck::emitDiagnosticsMalloc(const MatchFinder::MatchResult &Result, string allocnodebind, string typenodebind, string declnodebind) {
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

      // SmallString<200> pathVector;
      //   std::cout << "FILENAME: "
      //             << pathVector.c_str() + fsrcloc.getFileEntry()->getName().str()
      //             << ": " << line << endl;

      // std::cout << "DeclName: " << declnode->getNameAsString() << endl;
      int offset = declnode->getNameAsString().size();

#ifndef MALLOCCHECKER_TEMPLATE
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
#ifdef MALLOCCHECKER_TEMPLATE      
      diag(mnode->getExprLoc().getLocWithOffset(offset), "insert type here",
          DiagnosticIDs::Error)
          << FixItHint::CreateInsertion(
                mnode->getExprLoc().getLocWithOffset(offset),
                "<" + type + ", " + to_string(line) + ", MACRO_GET_STR(\"" + FileName + "\")" +
                      ">");
#endif // TEMPLATE
    }
  }
}

void MalloccheckerCheck::emitDiagnosticsNew(const MatchFinder::MatchResult &Result, string newbind) {
  const clang::CXXNewExpr* node =
      Result.Nodes.getNodeAs<clang::CXXNewExpr>(newbind);

  if (node) {
    if (node->getNumPlacementArgs() == 0) {
      diag(node->getExprLoc(), "insert MemStamp",
            DiagnosticIDs::Error)
            << FixItHint::CreateInsertion(
                  node->getExprLoc(),
                  "MemStamp((__FILE__), (__LINE__)) * ");
    }
    else if (node->getNumPlacementArgs() > 0) {
      std::string type = node->getAllocatedType().getUnqualifiedType().getAsString();
      std::string out = "MemStamp((__FILE__), (__LINE__)) * (" + type + "*) ";
      diag(node->getExprLoc(), "insert MemStamp (placement new)",
            DiagnosticIDs::Error)
            << FixItHint::CreateInsertion(
                  node->getExprLoc(),
                  out);
    }
  }
}

void MalloccheckerCheck::check(const MatchFinder::MatchResult &Result) {
  // FIXME: Add callback implementation.
  // std::cout << "CHECK\n" << std::endl;

  MalloccheckerCheck::emitDiagnosticsMalloc(Result, "sizeofmalloc", "sizeof-arg-type", "fdeclsizeofmalloc");
  MalloccheckerCheck::emitDiagnosticsMalloc(Result, "lhsmalloc", "lhs-type", "fdecllhsmalloc");
  MalloccheckerCheck::emitDiagnosticsMalloc(Result, "declmalloc", "decltype", "fdeclmalloc");

#ifdef MALLOCCHECKER_TEMPLATE  
  MalloccheckerCheck::emitDiagnosticsNew(Result, "newExpr");
#endif
}

} // namespace misc
} // namespace tidy
} // namespace clang
