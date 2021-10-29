#include "memhook_interface.h"
#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>
#include <unistd.h>
#include <time.h>
#include <immintrin.h>
#include <random>

#define THREAD_TEST_NUM 10
//#include "a.h"

using namespace std;

typedef struct tall{
int a;
int b;
}Tall;

class Stack{
private:

  pthread_mutex_t lock;
  struct Node{
    //data
    int *int_test_ptr;
    tall *tall_test_ptr;
    char *char_test_ptr;
    int key;
    Node * next;
    Node * prev;
  };

  Node *Top_Node;
public:
  Stack(){
    Top_Node = NULL;
    pthread_mutex_init(&lock, NULL);
  }

  void allocate_test(){
    int * int_test_ptr = (int*)malloc(sizeof(int));
    //Tall * tall_test_ptr = (tall*)malloc<tall*>(sizeof(tall));
    char * char_ptr = new char;

    //printf("finished allocation test\n");
  }

  void push(int val){
    pthread_mutex_lock(&lock);
    //printf("inside push function acquired lock \n");
    if (Top_Node == NULL){
      Top_Node = new struct Node;
      Top_Node->prev = NULL;
      Top_Node->next = NULL;
      Top_Node->key = val;
      allocate_test();
      pthread_mutex_unlock(&lock);
      return;
    }
    Node * tmp = new struct Node;

    Top_Node->next=tmp;
    tmp->prev = Top_Node;
    tmp->next = NULL;
    tmp->key = val;

    Top_Node = tmp;
    allocate_test();
    pthread_mutex_unlock(&lock);
  }

  int pop(){
    pthread_mutex_lock(&lock);
    Node * tmp = Top_Node;
    int key_value = -1;

    if(Top_Node == NULL){
      pthread_mutex_unlock(&lock);
      return -1;
    }

    if(Top_Node->prev == NULL){
      key_value = Top_Node->key;
      Top_Node = NULL;
      pthread_mutex_unlock(&lock);
      free(tmp);
      return key_value;
    }

    Top_Node = Top_Node->prev;
    Top_Node->next = NULL;
    pthread_mutex_unlock(&lock);
    key_value = tmp->key;
    free(tmp);
    return key_value;
  }

};

Stack global_stack;

void * rand_thread_function(void *p){

  unsigned long long seed_rand_val = 0ULL;

  while(_rdrand64_step(&seed_rand_val) != 1){};

  mt19937 generator(seed_rand_val);


  if((generator()% 103993) >= 51996){
    global_stack.push(0);
    //printf("above half \n");
  }
  else{
    global_stack.pop();
    //printf("below half\n");
  }
  pthread_exit(NULL);
  return NULL;
}


int main() {
  printf("testing new stack \n");
  /*
  for(int i = 0; i < 10; i++){
  	global_stack.push(i);
  }

  for(int i = 0; i < 10; i++){
  	int val = global_stack.pop();
  	printf("%d \n", val);
  }*/

  pthread_t id[THREAD_TEST_NUM];
  for(int i = 0; i < THREAD_TEST_NUM; i++){
    pthread_create(&id[i], NULL, rand_thread_function, NULL);
  }

  for(int i = 0; i < THREAD_TEST_NUM; i++){
    pthread_join(id[i], NULL);
    printf("%d \n", i);
  }
  
  return 0;
}
