#include <stdlib.h>
#include <stdio.h>

#include "memhook.h"

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
    tall* r = (tall*)malloc(sizeof(tall));
    tall* q = new tall;
<<<<<<< HEAD
    
    //barfoo();
    
=======
>>>>>>> 27ab9c8e4aaa333b7401d70f1b109dc2ddc6c981
    // int* r = new int;
    // printf("flag: %d\n", flag);
    // }

    // for(int i = 0;i < 10000;i++) {
    // int* r = (int*)malloc(sizeof(int));
    // printf("flag: %d  %d\n", flag,s*r);
    // }
    return 0;
}