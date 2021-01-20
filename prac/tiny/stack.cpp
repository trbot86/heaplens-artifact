#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>
#include <unistd.h>
#include <time.h>
#include <immintrin.h>
#include <random>

//#include "memhook_interface.h"

#define THREAD_TEST_NUM 1
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

    printf("finished allocation test\n");
  }

  void push(){
    pthread_mutex_lock(&lock);
    printf("inside push function acquired lock \n");
    if (Top_Node == NULL){
      Top_Node = new struct Node;
      Top_Node->prev = NULL;
      Top_Node->next = NULL;
      allocate_test();
      pthread_mutex_unlock(&lock);
      return;
    }
    Node * tmp = new struct Node;

    Top_Node->next=tmp;
    tmp->prev = Top_Node;
    tmp->next = NULL;

    Top_Node = tmp;
    allocate_test();
    pthread_mutex_unlock(&lock);
  }

  void pop(){
    pthread_mutex_lock(&lock);
    Node * tmp = Top_Node;
    if(Top_Node == NULL){
      pthread_mutex_unlock(&lock);
      return;
    }

    if(Top_Node->prev == NULL){
      Top_Node = NULL;
      free(tmp);
      pthread_mutex_unlock(&lock);
      return;
    }

    Top_Node = Top_Node->prev;
    Top_Node->next = NULL;
    free(tmp);

    pthread_mutex_unlock(&lock);
  }

};

Stack global_stack;

void * thread_function(void *p){
  printf("inside thread function \n");
  global_stack.push();

  sleep(rand());
  //sleep(5);
  global_stack.pop();
  pthread_exit(NULL);
}


void * rand_thread_function(void *p){

  unsigned long long seed_rand_val = 0ULL;

  while(_rdrand64_step(&seed_rand_val) != 1){};

  mt19937 generator(seed_rand_val);


  if((generator()% 103993) >= 51996){
    global_stack.push();
    printf("above half \n");
  }
  else{
    global_stack.pop();
    printf("below half\n");
  }
  pthread_exit(NULL);
  return NULL;
}


int main() {
  printf("testing new stack \n");

  pthread_t id[THREAD_TEST_NUM];

  for(int i = 0; i < THREAD_TEST_NUM; i++){
    pthread_create(&id[i], NULL, rand_thread_function, NULL);
  }

  for(int i = 0; i < THREAD_TEST_NUM; i++){
    pthread_join(id[i], NULL);
  }

    return 0;
}
