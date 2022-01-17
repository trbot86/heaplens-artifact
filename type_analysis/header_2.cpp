// ****************************************************************
// This file is a sample file to test the limits of the tool in C++
// ****************************************************************

// #include <iostream>
#include <stdlib.h>
#include "header.h"

int main() {
  mem_alloc m;
  m.alloc<char>(sizeof(char));
  return 0;
}