#include <iostream>
#include "memhook.h"

void foo1 () {
    (int*)malloc(sizeof(int));
    return;
}
