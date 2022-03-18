// ****************************************************************
// This file is a sample file to test the limits of the tool in C++
// ****************************************************************

// #include <iostream>
#include <stdlib.h>
#include "header.h"

int main() {
  mem_alloc m;
  m.alloc<char, 11, MACRO_GET_STR("header_2.cpp")>(sizeof(char));
  return 0;
}