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

// void* (*orig_malloc)(size_t);

struct slot;
struct info_t;
class ThreadExiter;
typedef map<type_index, const char*> type_map;
typedef set<const char*> filenameset;

extern void   (*next_free)(void *ptr);
extern void * (*next_malloc)(size_t size);
extern void * (*next_calloc)(size_t nmemb, size_t size);

extern thread_local int iter;

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


extern MemStampCollector collector;

/*Iterator for individual thread allocation in
* tracking data structure
*/
extern thread_local int it;

//Keeps the total number of concurrent threads
extern int arrayCount;

extern thread_local bool setup;

extern type_map tmap;

extern filenameset fset;

//Local array tracking a thread's allocations
extern thread_local info_t* myArray;

extern thread_local ThreadExiter exiter;

inline uint64_t get_server_clock() {
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

void printstats();
int get_slot(thread::id id);
void insert_type(void *p, const MemStamp &stamp, const type_index);
void insert_info(size_t size, void* ptr, type_index tindex);

void   (memhook_free)(void *ptr, bool log);
void *memhook_malloc(size_t size, bool log);

template <typename T>
T malloc(size_t size, bool fakearg=true);

template <class T>
inline T* operator * (const MemStamp &stamp, T *p) {
    collector.update(stamp.filename, stamp.lineNum, type_index(typeid(T)));
    // insert_type(p, stamp, type_index(typeid(T)));
    return p;
}

template <typename T>
T malloc(size_t size, bool fakearg) {
    T ptr = (T)memhook_malloc(size, true);
    collector.update("specialfile", 0, type_index(typeid(T)));
    if(ptr == NULL) throw bad_alloc();

    // insert_info(size, ptr, type_index(typeid(T)));
    return ptr;
}

#define SIFTER_NEW MemStamp(__FILE__, __LINE__) * new
#define new SIFTER_NEW
