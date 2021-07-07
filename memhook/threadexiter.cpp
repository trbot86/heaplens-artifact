#include <cstdio>
#include "threadexiter.h"
     ThreadExiter::ThreadExiter(){
      printf("Constructer has been called \n");
    }

    ThreadExiter::~ThreadExiter()
    {
      printf("Destructor has been called \n");
      // sarr[iter].occupied = false;
    }
     void  ThreadExiter::add()
    {
      printf("thread exiter: add\n");
      // exit_funcs.push(std::move(func));
    }