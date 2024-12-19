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
  ClangTidyToolMain.cpp
  )

#START ADDED?
# add_clang_library(clangTidyMain
#   ClangTidyMain.cpp

#   LINK_LIBS
#   clangTidy
#   ${ALL_CLANG_TIDY_CHECKS}

#   DEPENDS
#   omp_gen
#   )

# clang_target_link_libraries(clangTidyMain
#   PUBLIC
#   clangAST
#   clangASTMatchers
#   clangBasic
#   clangTooling
#   clangToolingCore
#   )
#END ADDED?

target_link_libraries(clang-tidy PRIVATE -L/usr/lib/llvm-14/lib)
target_link_libraries(clang-tidy PRIVATE -L/lib/llvm-14/lib)

clang_target_link_libraries(clang-tidy
  PRIVATE
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
  # LLVM-14
  )

# target_link_libraries(clang-tidy PUBLIC )

target_link_libraries(clang-tidy
  PRIVATE
  clangTidy
  clangTidyMain
  ${llvm_libs}
  ${ALL_CLANG_TIDY_CHECKS}
  -Wl,--end-group
  )