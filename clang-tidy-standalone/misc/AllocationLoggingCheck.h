//===--- AllocationLoggingCheck.h - clang-tidy ------------------*- C++ -*-===//
//
// Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
//
//===----------------------------------------------------------------------===//

#ifndef LLVM_CLANG_TOOLS_EXTRA_CLANG_TIDY_MISC_ALLOCATIONLOGGINGCHECK_H
#define LLVM_CLANG_TOOLS_EXTRA_CLANG_TIDY_MISC_ALLOCATIONLOGGINGCHECK_H

// #include "../utils/TransformerClangTidyCheck.h"
// #include "clang/Tooling/Transformer/Stencil.h"
#include "../ClangTidyCheck.h"

namespace clang {
namespace tidy {
namespace misc {

/// FIXME: Write a short description.
///
/// For the user-facing documentation see:
/// http://clang.llvm.org/extra/clang-tidy/checks/misc-allocation-logging.html
class AllocationLoggingCheck : public ClangTidyCheck {
public:
  AllocationLoggingCheck(StringRef Name, ClangTidyContext *Context) : ClangTidyCheck(Name, Context) {}

  void registerMatchers(ast_matchers::MatchFinder *Finder) override;
  void check(const ast_matchers::MatchFinder::MatchResult &Result) override;
private:
  void emitDiagnosticsMalloc(const ast_matchers::MatchFinder::MatchResult &Result, std::string allocnodebind, std::string typenodebind, std::string declnodebind);
  void emitDiagnosticsNew(const ast_matchers::MatchFinder::MatchResult &Result, std::string newbind);
};

} // namespace misc
} // namespace tidy
} // namespace clang

#endif // LLVM_CLANG_TOOLS_EXTRA_CLANG_TIDY_MISC_ALLOCATIONLOGGINGCHECK_H
