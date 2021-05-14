#include <stdlib.h>
#include <stdio.h>

#include "memhook_interface.h"
#include "a.h"

struct tall {
int a;
int b;
};

int main() {
    // int* p = (int*)malloc<int*>(sizeof(int));
    // for(int i = 0;i < 10000;i++) {
    // cout << "hello";
    int* p = (int*)malloc(sizeof(int));
    struct tall* r = (struct tall*)malloc(sizeof(struct tall));

    if(1) {

    } else {

    }
    // tall* q = new tall;
    // int* r = new int;
    // printf("flag: %d\n", flag);
    // }

    // for(int i = 0;i < 10000;i++) {
    // int* r = (int*)malloc(sizeof(int));
    // printf("flag: %d  %d\n", flag,s*r);
    // }
    return 0;
}