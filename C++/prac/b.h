#include "memhook.h"
#include <iostream>

struct somerandomstruct {
    int af;
    char yulongtea;
};

void goo1 (){
    (somerandomstruct*)malloc(sizeof(somerandomstruct));
    int* jj = new int;
    return;
}
