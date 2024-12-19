# llvm_map_components_to_libnames(LLVM_LINK_COMPONENTS
#   FrontendOpenMP
#   Support
#   )

add_clang_library(clangTidyUtils
  IncludeInserter.cpp
  IncludeSorter.cpp
  TransformerClangTidyCheck.cpp

  LINK_LIBS
  clangTidy

  DEPENDS
  omp_gen
  )

clang_target_link_libraries(clangTidyUtils
  PRIVATE
  clangAST
  clangASTMatchers
  clangBasic
  clangLex
  clangSema
  clangTransformer
  )
