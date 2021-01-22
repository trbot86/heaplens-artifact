// mention Curtis Bartley
#pragma once

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

#define BACKTRACE_DEPTH 2
#ifndef MAX_THREADS
    #define MAX_THREADS 8
#endif
#define MAX_TRACK 1000000
#define MAX_TYPE_LENGTH 1000
#define PADDING 64

using namespace std;

struct slot;
struct info_t;
class ThreadExiter;
typedef map<type_index, const char*> type_map;
typedef set<const char*> filenameset;

/*
After some further refactoring we might be able to remove this class declaration from memhook.h
*/
class MemStamp
{
    public:
        char const * const filename;
        int const lineNum;
    public:
        MemStamp(char const *filename, int lineNum);
        ~MemStamp();
};

class MemStampCollector {
private:
    slot* sarr;
    info_t* allArrays;

    int get_slot(thread::id id);

public:
    MemStampCollector();

    ~MemStampCollector();

    void add(uint64_t timestamp, size_t size, void * addr, bool typeofop);
    void update(const char * file, unsigned int line, type_index tindex);
    void threadexit();
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

// #warning This binary is being compiled with memhook. Running it will produce a text file that should be provided as an argument to the shell script for step3.

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
    char padding[PADDING];

    info_t() : file(nullptr), tindex(typeid(void)), line(0), timestamp(0), size(0), addr(nullptr) {}
};

thread_local int iter = 0;

/*Iterator for individual thread allocation in
* tracking data structure
*/

thread_local int it;
thread_local info_t* myArray = nullptr;

ostream& operator << (ostream& os, info_t& info);

int MemStampCollector::get_slot(thread::id id) {
  while(true) {
    while(sarr[iter].occupied) {
      // cout << "while" << endl;
      iter = (iter+1)%MAX_THREADS;
    }
    
    if(__sync_bool_compare_and_swap(&sarr[iter].occupied, false, true)) {
      // cout << iter << endl;
      sarr[iter].id = id;
      it = sarr[iter].offset;
      return iter;
    }
    // cout << "failed\n";
    iter = (iter+1)%MAX_THREADS;
  }
}


MemStampCollector::MemStampCollector() {
  allArrays = (info_t*)next_calloc(1, MAX_THREADS*MAX_TRACK*sizeof(info_t));
  sarr = (slot*)next_calloc(1, MAX_THREADS*sizeof(slot));
}

MemStampCollector::~MemStampCollector() {
  it = INT_MAX;
  ofstream myfile("info_t_dump.txt", ios_base::out | ios_base::app);

  int status;
  char *demangled_name;

  for (int i = 0; i < MAX_TRACK * MAX_THREADS; i++)
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
    myArray = allArrays + MAX_TRACK*result;
  }
  
  if(it < MAX_TRACK) {
    myArray[it].timestamp = memhook_get_server_clock();
    myArray[it].size = size;
    myArray[it].addr = addr;
    myArray[it].typeofop = typeofop;
    it++;
  }
}

void MemStampCollector::update(const char * file, unsigned int line, type_index tindex) {      
    myArray[it-1].file = file;
    myArray[it-1].line = line;
    myArray[it-1].tindex = tindex;
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
      // sarr[iter].occupied = false;
    }
    void add()
    {
      // exit_funcs.push(std::move(func));
    }
  };

//Keeps the total number of concurrent threads
int arrayCount = 0;

thread_local bool setup = false;

filenameset fset;

thread_local ThreadExiter exiter;
