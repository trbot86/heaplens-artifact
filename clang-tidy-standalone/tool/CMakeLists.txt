llvm_map_components_to_libnames(llvm_libs
  support
  core
  AllTargetsAsmParsers
  AllTargetsDescs
  AllTargetsInfos
  FrontendOpenMP
  Option
  )

add_clang_tool(clang-tidy
  ClangTidyMain.cpp
  )

target_link_libraries(clang-tidy PUBLIC -L/usr/lib/llvm-10/lib)
target_link_libraries(clang-tidy PUBLIC -L/lib/llvm-10/lib)

clang_target_link_libraries(clang-tidy
  PUBLIC
  -Wl,--start-group
  clangAnalysis
  clangAST
  clangASTMatchers
  clangBasic
  clangCrossTU
  clangDriver
  clangEdit
  clangFormat
  clangFrontend
  clangIndex
  clangParse
  clangRewrite
  clangSerialization
  clangSema
  clangStaticAnalyzerCore
  clangStaticAnalyzerCheckers
  clangStaticAnalyzerFrontend
  clangTooling
  clangToolingCore
  clangToolingInclusions
  clangLex
  LLVM-10
  )

# target_link_libraries(clang-tidy PUBLIC )

target_link_libraries(clang-tidy
  PUBLIC
  clangTidy
  ${llvm_libs}
  ${ALL_CLANG_TIDY_CHECKS}
  -Wl,--end-group
  )