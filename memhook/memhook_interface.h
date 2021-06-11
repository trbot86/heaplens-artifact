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
#include "threadexiter.h"
//#include <execinfo.h>
//#include <cxxabi.h>
//#include <dlfcn.h>


using namespace std;

// void* (*orig_malloc)(size_t);

//extern struct slot;
//extern struct info_t;
//extern class ThreadExiter;

//struct slot;
//struct info_t;

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
  //private:
  // slot* sarr;
  //info_t* allArrays;

  //int get_slot(thread::id id);

public:
    // MemStampCollector();

    //~MemStampCollector();

    //void add(uint64_t timestamp, size_t size, void * addr, bool typeofop);
    void update(const char * file, unsigned int line, type_index tindex);
    //void threadexit();
};

extern MemStampCollector collector;
extern thread_local ThreadExiter exiter;

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
