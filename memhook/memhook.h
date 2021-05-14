// mention Curtis Bartley
#ifndef __MEMHOOK_H
#define __MEMHOOK_H
// #pragma once

#include <iostream>
#include <new>
#include <typeinfo>
#include <typeindex>
#include <bits/stdc++.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <execinfo.h>
#include <cxxabi.h>
#include <dlfcn.h>

#define MEMHOOK_BACKTRACE_DEPTH 2
#ifndef MEMHOOK_MAX_THREADS
    #define MEMHOOK_MAX_THREADS 8
#endif
#define MEMHOOK_MAX_TRACK 1000000
#define MEMHOOK_MAX_TYPE_LENGTH 1000
#define MEMHOOK_MAX_RETRY 10
// #define PADDING 64

using namespace std;

struct slot;
struct info_t;
class ThreadExiter;
typedef map<type_index, const char*> type_map;
typedef set<const char*> filenameset;

class memhook_memory_pool {
  int array_count;
  
  public:
    virtual void add(info_t* logarray);
    virtual info_t* pop();
    virtual void dumptodisk();
};

inline uint64_t memhook_get_server_clock() {
#if defined(__i386__)
    uint64_t ret;
    __asm__ __volatile__("rdtsc" : "=A" (ret));
#elif defined(__x86_64__)
    unsigned hi, lo;
    __asm__ __volatile__ ("rdtsc" : "=a"(lo), "=d"(hi));
    uint64_t ret = ( (uint64_t)lo)|( ((uint64_t)hi)<<32 );
#else 
    #error Must support RDTSC instruction! Sorry...
#endif
    return ret;
}

type_map tmap;
int get_slot(thread::id id);
void insert_type(void *p, const MemStamp &stamp, const type_index);
void insert_info(size_t size, void* ptr, type_index tindex);

void   (memhook_free)(void *ptr, bool log);
void *memhook_malloc(size_t size, bool log);

#warning This binary is being compiled with memhook. Running it will produce a text file (info_t_dump.txt) that should be provided as an argument to the shell script for step3.

void   (*next_free)(void *ptr);
void * (*next_malloc)(size_t size);
void * (*next_calloc)(size_t nmemb, size_t size);

struct slot {
	volatile bool occupied;
	thread::id id;
	int offset;
  char padding[128];
};

MemStamp::MemStamp(char const *filename, int lineNum)
    : filename(filename), lineNum(lineNum) { }
MemStamp::~MemStamp() { }

struct info_t {
    const char* file;
    type_index tindex;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;
    // char padding[PADDING];

    info_t() : file(nullptr), tindex(typeid(void)), line(0), timestamp(0), size(0), addr(nullptr) {}
};

thread_local int iter = 0;

/*Iterator for individual thread allocation in
* tracking data structure
*/

thread_local int it = 0;
thread_local info_t* myArray = nullptr;
thread_local int max_retry = 0;

ostream& operator << (ostream& os, info_t& info);

int MemStampCollector::get_slot(thread::id id) {
  max_retry = 0;
  while(max_retry < MEMHOOK_MAX_RETRY) {
    while(sarr[iter].occupied && (max_retry < MEMHOOK_MAX_RETRY)) {
      // cout << "while" << endl;
      iter = (iter+1)%MEMHOOK_MAX_THREADS;
      max_retry++;
    }
    
    if(__sync_bool_compare_and_swap(&sarr[iter].occupied, false, true)) {
      // cout << iter << endl;
      sarr[iter].id = id;
      it = sarr[iter].offset;
      return iter;
    }
    // cout << "failed\n";
    iter = (iter+1)%MEMHOOK_MAX_THREADS;
    max_retry++;
  }
  return -1;
}


MemStampCollector::MemStampCollector() {
  allArrays = (info_t*)next_calloc(1, MEMHOOK_MAX_THREADS*MEMHOOK_MAX_TRACK*sizeof(info_t));

  if(allArrays == NULL) {
    printf("[Integer overflow]: either calloc failed or integer overflow. reduce MEMHOOK_MAX_TRACK or MEMHOOK_MAX_THREADS\n");
    exit(0);
  }

  sarr = (slot*)next_calloc(1, MEMHOOK_MAX_THREADS*sizeof(slot));

  if(sarr == NULL) {
    printf("[Integer Overflow]: either calloc failed or integer overflow. reduce MAX_THREADS\n");
  }
}

MemStampCollector::~MemStampCollector() {
  it = INT_MAX;
  stringstream threadid_ss;
  threadid_ss << this_thread::get_id();
  ofstream myfile(threadid_ss.str() + "_info_t_dump.txt", ios_base::out | ios_base::app);
  int status;
  char *demangled_name;

  for (int i = 0; i < MEMHOOK_MAX_TRACK * MEMHOOK_MAX_THREADS; i++)
  {
    if (allArrays[i].addr == nullptr)
      continue;
    else if (allArrays[i].file && allArrays[i].typeofop && !tmap.count(allArrays[i].tindex))
    {
      demangled_name = abi::__cxa_demangle(allArrays[i].tindex.name(), 0, 0, &status);
      tmap[allArrays[i].tindex] = demangled_name;
    }

    myfile << allArrays[i];
  }
}

void MemStampCollector::add(uint64_t timestamp, size_t size, void * addr, bool typeofop) {
  if(myArray == nullptr) {
    thread_local int result = get_slot(this_thread::get_id());
    it = sarr[result].offset;
    myArray = allArrays + MEMHOOK_MAX_TRACK*result;
  }
  
  if(it >= 0 && it < MEMHOOK_MAX_TRACK) {
    myArray[it].timestamp = memhook_get_server_clock();
    myArray[it].size = size;
    myArray[it].addr = addr;
    myArray[it].typeofop = typeofop;
    it++;
  }
  else {
    //printf("[MEMHOOK_MAX_TRACK overflow or MEMHOOK_MAX_RETRY exceeded it: %d]\n", it);
    // it = 0;
  }
}

void MemStampCollector::update(const char * file, unsigned int line, type_index tindex) {      
    //NORMALLY UPDATE SHOULD BE CALLED AFTER ADD, BUT IN MEMHOOK_MALLOC WHILE INITIALISED IS FALSE, ADD IS NOT CALLED
    //BECAUSE OF THIS, UPDATE CAN BE CALLED WHEN IT-1 < 0. WE SHOULD IGNORE SUCH CALLS (WHICH MAINLY OCCUR DURING DL_INIT)
    if(it-1 < MEMHOOK_MAX_TRACK && it-1 >= 0) {
      myArray[it-1].file = file;
      myArray[it-1].line = line;
      myArray[it-1].tindex = tindex;
    }
    else {
      //printf("[it: %d]\n", it);
      // it = 0;
    }
}

void MemStampCollector::threadexit() {
    sarr[iter].offset = it++;
    __sync_bool_compare_and_swap(&sarr[iter].occupied, true, false);
}

MemStampCollector collector;

class ThreadExiter
  {
    public:
    ThreadExiter() = default;
    
    ThreadExiter(ThreadExiter const&) = delete;
    
    void operator=(ThreadExiter const&) = delete;
    
    ~ThreadExiter()
    {
      collector.threadexit();
    }
    void add()
    {

    }
  };

//Keeps the total number of concurrent threads
int arrayCount = 0;

thread_local bool setup = false;

filenameset fset;

thread_local ThreadExiter exiter;
#endif