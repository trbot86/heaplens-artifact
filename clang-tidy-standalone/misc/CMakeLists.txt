add_clang_library(clangTidyMiscModule
  AllocationLoggingCheck.cpp
  MiscTidyModule.cpp

  # LINK_LIBS
  # clangAnalysis
  # clangAST
  # clangASTMatchers
  # clangBasic
  # clangLex
  # clangSerialization
  # clangTidy
  # clangTidyUtils
  # clangTooling

  DEPENDS
  omp_gen
  )

clang_target_link_libraries(clangTidyMiscModule
  PRIVATE
  clangAnalysis
  clangAST
  clangASTMatchers
  clangBasic
  clangLex
  clangSerialization
  clangTooling
  clangTidy
  # clangTidyUtils
  )

option(CPP_TEMPLATE "Specify whether the target application supports templating." OFF)

if(CPP_TEMPLATE)
  add_definitions(-DALLOCLOGGING_TEMPLATE)
endif(CPP_TEMPLATE)
