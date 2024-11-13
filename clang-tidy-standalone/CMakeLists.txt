project(clang-tidy-standalone)
cmake_minimum_required(VERSION 3.22.1)

list(APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_LIST_DIR}/cmake)
include(clang_wrapper)
include(utils)

in_source_build_guard()
set_default_build_type(Debug)

find_package(LLVM 14.0.6 EXACT REQUIRED CONFIG)

set(LLVM_PATH /usr/lib/llvm-14)

include_directories("${LLVM_INCLUDE_DIRS}")
# link_directories("${LLVM_LIBRARY_DIRS}")
# include_directories(${LLVM_PATH}/include)
link_directories(${LLVM_PATH}/lib)


set(CMAKE_LIBRARY_PATH "/usr/lib/llvm-14/lib")

# Checks.
# If you add a check, also add it to ClangTidyForceLinker.h in this directory.
add_subdirectory(misc)
set(ALL_CLANG_TIDY_CHECKS
  clangTidyMiscModule
  )

# Other subtargets. These may reference ALL_CLANG_TIDY_CHECKS
# and must be below its definition.
add_subdirectory(tool)
# add_subdirectory(utils)
