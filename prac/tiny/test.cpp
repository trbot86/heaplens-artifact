#include <stdlib.h>
#include <stdio.h>

#include "memhook_extern.h"

struct tall {
int a;
int b;
};

int main() {
    // int* p = (int*)malloc<int*>(sizeof(int));
    // for(int i = 0;i < 10000;i++) {
    // cout << "hello";
    int* p = (int*)malloc(sizeof(int));
    float* r = (float*)malloc<float*>(sizeof(float));
    int* q = new int;
    // int* r = new int;
    // printf("flag: %d\n", flag);
    // }

    // for(int i = 0;i < 10000;i++) {
    // int* r = (int*)malloc(sizeof(int));
    // printf("flag: %d  %d\n", flag,s*r);
    // }
    return 0;
}