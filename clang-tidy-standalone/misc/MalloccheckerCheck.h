#include "memhook_interface.h"
//===--- MalloccheckerCheck.h - clang-tidy ----------------------*- C++ -*-===//
//
// Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
//
//===----------------------------------------------------------------------===//

#ifndef LLVM_CLANG_TOOLS_EXTRA_CLANG_TIDY_MISC_MALLOCCHECKERCHECK_H
#define LLVM_CLANG_TOOLS_EXTRA_CLANG_TIDY_MISC_MALLOCCHECKERCHECK_H

#include "../ClangTidyCheck.h"

namespace clang {
namespace tidy {
namespace misc {

/// FIXME: Write a short description.
/// This check "templatizes" any allocation function with the type of memory it allocates
/// For the user-facing documentation see:
/// http://clang.llvm.org/extra/clang-tidy/checks/misc-MallocChecker.html
class MalloccheckerCheck : public ClangTidyCheck {
public:
  MalloccheckerCheck(StringRef Name, ClangTidyContext *Context)
      : ClangTidyCheck(Name, Context) {}
  void registerMatchers(ast_matchers::MatchFinder *Finder) override;
  void check(const ast_matchers::MatchFinder::MatchResult &Result) override;
private:
  void emitDiagnostics(const ast_matchers::MatchFinder::MatchResult &Result, std::string allocnodebind, std::string typenodebind, std::string declnodebind);
};

} // namespace misc
} // namespace tidy
} // namespace clang

#endif // LLVM_CLANG_TOOLS_EXTRA_CLANG_TIDY_MISC_MALLOCCHECKERCHECK_H
