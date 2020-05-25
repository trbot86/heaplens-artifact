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

#define BACKTRACE_DEPTH 2
#ifndef MAX_THREADS
    #define MAX_THREADS 16
#endif
#define MAX_TRACK 1000000
#define MAX_TYPE_LENGTH 1000
#define PADDING 64

using namespace std;

struct slot;
class MemStamp;
struct info_t;
class ThreadExiter;
typedef map<type_index, const char*> type_map;
typedef set<const char*> filenameset;

extern thread_local int iter;

/*Iterator for individual thread allocation in
* tracking data structure
*/
extern thread_local int it;

extern slot *sarr;

//Keeps the total number of concurrent threads
extern int arrayCount;

extern thread_local bool setup;

extern type_map tmap;

extern filenameset fset;

//Global array for tracking all allocations
extern info_t* allArrays;

//Local array tracking a thread's allocations
extern thread_local info_t* myArray;

extern thread_local ThreadExiter exiter;

inline uint64_t get_server_clock();
__attribute__ ((constructor)) void allocArray();
__attribute__ ((destructor)) void dumpentirestatstofile2();
void printstats();
int get_slot(thread::id id);
// void dumpentirestatstofile(const char* file);
void dumpstatstofile(const char *file);
void insert_type(void *p, const MemStamp &stamp, const type_index);
void insert_info(size_t size, void* ptr, type_index tindex);

template <typename T>
T malloc(size_t size, bool fakearg=true);

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
