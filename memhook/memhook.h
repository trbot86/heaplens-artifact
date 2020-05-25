// mention Curtis Bartley
#pragma once

#include "memhook_extern.h"

// #warning This binary is being compiled with memhook. Running it will produce a text file that should be provided as an argument to the shell script for step3.

struct slot {
	volatile bool occupied;
	thread::id id;
	int offset;
};

class MemStamp
{
    public:
        char const * const filename;
        int const lineNum;
    public:
        MemStamp(char const *filename, int lineNum)
            : filename(filename), lineNum(lineNum) { }
        ~MemStamp() { }
};

struct info_t {
    const char* file;
    type_index tindex;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;
    char padding[PADDING];

    info_t() : file(nullptr), tindex(typeid(void)), line(0), timestamp(0), size(0), addr(nullptr) {}
};

thread_local int iter = 0;

/*Iterator for individual thread allocation in
* tracking data structure
*/
thread_local int it = 0;

class ThreadExiter
  {
    // std::stack<std::function<void()>> exit_funcs;
  public:
    ThreadExiter() = default;
    ThreadExiter(ThreadExiter const&) = delete;
    void operator=(ThreadExiter const&) = delete;
    ~ThreadExiter()
    {
      // while(!exit_funcs.empty())
      // {
      //   exit_funcs.top()();
      //   exit_funcs.pop();
      // }
      // cout << "ThreadExiter dtor\n";
      sarr[iter].offset = it++;
      sarr[iter].occupied = false;
    }
    void add()
    {
      // exit_funcs.push(std::move(func));
    }
  };

//Keeps the total number of concurrent threads
int arrayCount = 0;

thread_local bool setup = false;

type_map tmap;

filenameset fset;

//Global array for tracking all allocations
info_t* allArrays;

//Local array tracking a thread's allocations
thread_local info_t* myArray;

thread_local ThreadExiter exiter;
