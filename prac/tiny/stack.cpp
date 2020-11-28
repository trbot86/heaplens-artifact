
#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>
#include <unistd.h>
#include <time.h>

#include "memhook_interface.h"

#define THREAD_TEST_NUM 1
//#include "a.h"

struct tall {
int a;
int b;
};

class Stack{
private:

  pthread_mutex_t lock;
  struct node{
    //data
    int *int_test_ptr;
    tall *tall_test_ptr;
    char *char_test_ptr;

    node * next;
    node * prev;
  };

  Node *Top_Node;
public:
  Stack(){
    Top_of_stack = NULL;
    pthread_mutex_init(&lock, NULL);
  }

  void allocate_test(){
    int_test_ptr = (int*)malloc(sizeof(int));
    tall_test_ptr = (tall*)malloc<tail*>(sizeof(tall));
    char_ptr = new char;
  }

  void push(){
    if (Top_Node == NULL){
      Top_Node = new struct node;
      Top_Node->prev = NULL;
      Top_Node->next = NULL;
      allocate_test();
      return;
    }
    Node * tmp = new struct node;

    Top_Node->next=tmp;
    tmp->prev = Top_Node;
    tmp->next = NULL;

    Top_Node = tmp;
    allocate_test();
  }

  void pop(){
    Node * tmp = Top_Node;
    if(Top_Node == NULL){
      return;
    }
    Top_Node = Top_Node->prev;
    Top_Node->next = NULL;

    free(tmp);
  }

};

Stack global_stack;

void * thread_function(void *p){
  pthread_mutex_lock(&lock);
  global_stack.push();

  sleep(rand());

  global_stack.pop();
  pthread_mutex_unlock(&lock);
  pthread_exit(NULL);
}

int main() {

  pthread_t id[THREAD_TEST_NUM];

  srand(time(0));

  for(int i = 0; i < THREAD_TEST_NUM; i++){
    pthread_create(&id[i], NULL, thread_function, NULL);
  }

    return 0;
}
