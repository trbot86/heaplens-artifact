#include <iostream>

struct somerandomstruct {
    int af;
    char yulongtea;
};

void goo1 (){
    (somerandomstruct*)malloc(sizeof(somerandomstruct));
    return;
}
