add_clang_library(clangTidyMiscModule
  MalloccheckerCheck.cpp
  MiscTidyModule.cpp

  LINK_LIBS
  clangAnalysis
  clangAST
  clangASTMatchers
  clangBasic
  clangLex
  clangSerialization
  clangTidy
  clangTidyUtils
  clangTooling
  )

option(CPP_TEMPLATE "Specify whether the target application supports templating." OFF)

if(CPP_TEMPLATE)
  add_definitions(-DMALLOCCHECKER_NOTEMPLATE)
endif(CPP_TEMPLATE)
