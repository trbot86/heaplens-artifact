#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>
#include "memhook_interface.h"

<<<<<<< HEAD:prac/tiny/test.c
#include "memhook_interface.h"
#include "a.h"

=======
#define THREAD_COUNT 4
/*
>>>>>>> optimization-branch:prac/tiny/test.cpp
struct tall {
int a;
int b;
};*/

<<<<<<< HEAD:prac/tiny/test.c
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
=======

/*class ThreadExiter
{
public:
    ThreadExiter(){
        printf("Constructor call \n");
    }

    void test(){
    	//printf("hello \n");
    }

    ~ThreadExiter(){
        printf("Destructor call \n");
    }

};*/

//thread_local ThreadExiter thread_obj;


void * rand_thread_function(void *p){

    int* q = (int*)malloc(sizeof(int));
    //thread_obj.test();
    //printf("thread function called\n") ;
    malloc(50);
    //pthread_exit(NULL);
    //return NULL;
}

int main(int agrc, char **argv) {
    
    int* p = (int*)malloc(sizeof(int));

     pthread_t id[THREAD_COUNT];

    for(int i = 0; i < THREAD_COUNT; i++){
      pthread_create(&id[i], NULL, rand_thread_function, NULL);
    }

    /*
    for(int i = 0; i < THREAD_COUNT; i++){
      pthread_join(id[i], NULL);
      }*/

>>>>>>> optimization-branch:prac/tiny/test.cpp
    return 0;
}
