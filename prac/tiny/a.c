#include "memhook_interface.h"
// #pragma once
#include <stdlib.h>
#include <dlfcn.h>

#include "a.h"

int* foo() {
    int* ret = (int*)malloc(sizeof(int));
    return ret;
}