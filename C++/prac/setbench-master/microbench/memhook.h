// mention Curtis Bartley
#ifndef memhook_H
#define memhook_H

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

#define BACKTRACE_DEPTH 2
#define MAX_THREADS 100
#define MAX_TRACK 100000
#define MAX_TYPE_LENGTH 1000
#define PADDING 64

using namespace std;

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

static thread_local int iter = 0;

/*Iterator for individual thread allocation in
* tracking data structure
*/
static thread_local int it = 0;

extern slot *sarr;

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
static int arrayCount = 0;

thread_local static bool setup = false;

typedef map<type_index, const char*> type_map;

static type_map tmap;

typedef set<const char*> filenameset;

static filenameset fset;

//Global array for tracking all allocations
info_t* allArrays;

//Local array tracking a thread's allocations
thread_local info_t* myArray;

thread_local static ThreadExiter exiter;

inline uint64_t get_server_clock();
__attribute__ ((constructor)) void allocArray();
__attribute__ ((destructor)) void dumpentirestatstofile2();
void printstats();
int get_slot(thread::id id);
// void dumpentirestatstofile(const char* file);
void dumpstatstofile(const char *file);
void insert_type(void *p, const MemStamp &stamp, const type_index);
void insert_info(size_t size, void* ptr, type_index tindex);
template <typename T> T malloc(size_t size, bool fakearg=true);

template <class T>
inline T* operator * (const MemStamp &stamp, T *p) {
    insert_type(p, stamp, type_index(typeid(T)));
    return p;
}

template <typename T>
T malloc(size_t size, bool fakearg) {    
    T ptr = (T)std::malloc(size);
    if(ptr == NULL) throw bad_alloc();

    insert_info(size, ptr, type_index(typeid(T)));

    return ptr;
}

#define SIFTER_NEW MemStamp(__FILE__, __LINE__) * new
#define new SIFTER_NEW

#endif  