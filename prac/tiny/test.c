#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>
#include "memhook_interface.h"

#include "a.h"

#define THREAD_COUNT 4
/*
struct tall {
int a;
int b;
};*/

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

    return 0;
}
