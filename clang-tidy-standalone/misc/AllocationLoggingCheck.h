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
#include <fstream>

namespace clang {
namespace tidy {
namespace misc {

/// FIXME: Write a short description.
///
/// For the user-facing documentation see:
/// http://clang.llvm.org/extra/clang-tidy/checks/misc-allocation-logging.html
class AllocationLoggingCheck : public ClangTidyCheck {
private:
  std::unordered_map<std::string, uint16_t> filemap;
  const char* memhook_fileset_path;
#ifndef ALLOCLOGGING_TEMPLATE
  std::unordered_map<std::string, uint16_t> typemap;
  const char* memhook_typeset_path;
#endif
public:
  AllocationLoggingCheck(StringRef Name, ClangTidyContext *Context) : ClangTidyCheck(Name, Context),
                                                                      filemap{}
                                                                      #ifndef ALLOCLOGGING_TEMPLATE
                                                                      , typemap{}
                                                                      #endif
  {
    const char* fileset_env_path = std::getenv("MEMHOOK_OUTPUT_FILE_PATH");

    if (fileset_env_path) {
      memhook_fileset_path = fileset_env_path;
    }
    else {
      memhook_fileset_path = "/root/sifter/type_analysis/fileset_dump.txt";
    }

    std::ifstream fileset;
    fileset.open(memhook_fileset_path);

    std::string line;
    while (std::getline(fileset, line)) {
      size_t pos = line.find('|');
      filemap[line.substr(pos + 1)] = std::stoi(line.substr(0, pos));
    }

    fileset.close();
#ifndef ALLOCLOGGING_TEMPLATE
    const char* typeset_env_path = std::getenv("MEMHOOK_OUTPUT_TYPE_PATH");

    if (typeset_env_path) {
      memhook_typeset_path = typeset_env_path;
    }
    else {
      memhook_typeset_path = "/root/sifter/type_analysis/typeset_dump.txt";
    }

    std::ifstream typeset;
    typeset.open(memhook_typeset_path);

    while (std::getline(typeset, line)) {
      size_t pos = line.find('|');
      typemap[line.substr(pos + 1)] = std::stoi(line.substr(0, pos));
    }

    typeset.close();
#endif
  }

  ~AllocationLoggingCheck() {
    std::ofstream fileset;
    fileset.open(memhook_fileset_path, std::ofstream::out | std::ofstream::trunc);
    for (const auto &pair : filemap) {
        fileset << pair.second << "|" << pair.first << "\n";
    }

#ifndef ALLOCLOGGING_TEMPLATE
    std::ofstream typeset;
    typeset.open(memhook_typeset_path, std::ofstream::out | std::ofstream::trunc);
    for (const auto &pair : typemap) {
        typeset << pair.second << "|" << pair.first << "\n";
    }
#endif
  }

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
