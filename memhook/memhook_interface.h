// mention Curtis Bartley
#ifndef __MEMHOOK_INTERFACE_H
#define __MEMHOOK_INTERFACE_H
// #pragma once

//ASK ABOUT DIFFERENT IMPLEMENTATIONS OF BOOL IN C/C++. WILL THAT BE A PROBLEM?
#include <stdbool.h>
#include <stddef.h>
#ifdef __cplusplus

#include <iostream>
#include <new>
#include <typeinfo>
#include <typeindex>
#include <bits/stdc++.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
//#include <execinfo.h>
//#include <cxxabi.h>
//#include <dlfcn.h>

using namespace std;

#endif

#define PADDING 64

// void* (*orig_malloc)(size_t);

struct slot;
struct info_t;

// void *memhook_malloc(size_t size, bool log);

#ifdef __cplusplus
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
    void update(const char * file, unsigned int line, type_index* tindex);
    void threadexit();
};

extern MemStampCollector collector;

template <typename T>
T malloc(size_t size, bool fakearg=true);

template <class T>
inline T* operator * (const MemStamp &stamp, T *p) {
    type_index t = type_index(typeid(T));
    collector.update(stamp.filename, stamp.lineNum, &t);
    return p;
}

// template <typename T>
// T malloc(size_t size, bool fakearg) {
//     T ptr = (T)memhook_malloc(size, true);
//     type_index t = type_index(typeid(T));
//     collector.update("specialfile", 0, &t);
//     if(ptr == NULL) throw bad_alloc();
//     return ptr;
// }

#endif

#ifdef __cplusplus
extern "C" {
#endif

void* malloc_s(size_t, char*, int);

#ifdef __cplusplus
}
#endif

#define SIFTER_NEW MemStamp(__FILE__, __LINE__) * new
#define new SIFTER_NEW

#define malloc(s) malloc_s(s, __FILE__, __LINE__)
#endif          //__MEMHOOK_INTERFACE_H