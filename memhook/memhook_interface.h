// mention Curtis Bartley
#ifndef __MEMHOOK_INTERFACE_H
#define __MEMHOOK_INTERFACE_H
#pragma once

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
#include "memstamp.h"
//#include <execinfo.h>
//#include <cxxabi.h>
//#include <dlfcn.h>

using namespace std;

#endif

#define PADDING 64

struct slot;
struct info_t;

#ifdef __cplusplus
extern "C" {
#endif

void* malloc_s(size_t, char*, int);
extern void *memhook_malloc(size_t size, char* file, int line, bool log);

#define SIFTER_NEW MemStamp((__FILE__), (__LINE__)) * new
#define new SIFTER_NEW

#ifdef __cplusplus
}
#endif

#ifdef __cplusplus

extern MemStampCollector collector;
extern thread_local info_t unit_log;
extern thread_local unordered_set<const char*> threadFiles;
extern thread_local unordered_set<const char*> typeFiles;

// template <typename T>
// T malloc(size_t size, bool fakearg=true);

template <class T>
inline T* operator * (const MemStamp &stamp, T *p) {
    unit_log.file = "specialfile";
    unit_log.tindex_name = typeid(T).name();

    threadFiles.insert(unit_log.file);
    typeFiles.insert(unit_log.tindex_name);

    collector.copy(unit_log);
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

template <typename T, char* filename, int line>
T malloc(size_t size, bool fakearg) {
    T ptr = (T)memhook_malloc(size, filename, line, true);
    type_index t = type_index(typeid(T));

    typeFiles.insert(unit_log.tindex_name);

    collector.copy(unit_log);
    return ptr;
}

#endif

uint64_t memhook_get_server_clock();

#define malloc(s) malloc_s((s), (__FILE__), (__LINE__))
#endif          //__MEMHOOK_INTERFACE_H