// mention Curtis Bartley
#ifndef __MEMHOOK_INTERFACE_H
#define __MEMHOOK_INTERFACE_H
#pragma once

// ASK ABOUT DIFFERENT IMPLEMENTATIONS OF BOOL IN C/C++. WILL THAT BE A PROBLEM?
#include <stdbool.h>
#include <stdint.h>
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
#include "hash.h"
//#include <execinfo.h>
//#include <cxxabi.h>
//#include <dlfcn.h>

using namespace std;

#endif

#define PADDING 64

#define MACRO_GET_1(str, i) \
    (sizeof(str) > (i) ? str[(i)] : 0)

#define MACRO_GET_4(str, i)      \
    MACRO_GET_1(str, i + 0),     \
        MACRO_GET_1(str, i + 1), \
        MACRO_GET_1(str, i + 2), \
        MACRO_GET_1(str, i + 3)

#define MACRO_GET_16(str, i)     \
    MACRO_GET_4(str, i + 0),     \
        MACRO_GET_4(str, i + 4), \
        MACRO_GET_4(str, i + 8), \
        MACRO_GET_4(str, i + 12)

#define MACRO_GET_64(str, i)       \
    MACRO_GET_16(str, i + 0),      \
        MACRO_GET_16(str, i + 16), \
        MACRO_GET_16(str, i + 32), \
        MACRO_GET_16(str, i + 48)

#define MACRO_GET_STR(str) MACRO_GET_64(str, 0), 0

struct slot;
struct info_t;

#ifdef __cplusplus
extern "C"
{
#endif

    void *malloc_s(size_t, const char *, int);
    void free_s(void *, const char *, int);

// #define SIFTER_NEW
#define new MemStamp((__FILE__), (__LINE__)) * new
    // #define delete MemStamp((__FILE__), (__LINE__)) * delete

#ifdef __cplusplus
}
#endif

#ifdef __cplusplus

extern MemStampCollector collector;
extern thread_local info_t unit_log;
// extern thread_local unordered_set<const char*> threadFiles;
// extern thread_local unordered_set<const char*> typeFiles;
extern memhook_hashtable filetable;
extern memhook_hashtable typetable;
extern void *memhook_malloc(size_t size, const char *file, int line, bool log);

// template <typename T>
// T malloc(size_t size, bool fakearg=true);

template <class T>
inline T *operator*(const MemStamp &stamp, T *p)
{
    unit_log.file = filetable.insert(stamp.filename);
    unit_log.line = stamp.lineNum;
    unit_log.tindex_name = typetable.insert(typeid(T).name());

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

#if !(defined(_WIN32) && defined(_mm_malloc))
template <typename T, int line, char... filename>
static __inline__ void* __attribute__((__always_inline__, __nodebug__,
                                       __malloc__))
_mm_malloc(size_t __size, size_t __align)
{
    string filestring = {filename...};

    unit_log.file = filetable.insert(filestring.c_str());
    unit_log.tindex_name = typetable.insert(typeid(T).name());
    if (__align == 1)
    {
        void* ptr = memhook_malloc(__size, unit_log.file, line, true);
        collector.copy(unit_log);
        return ptr;
    }

    if (!(__align & (__align - 1)) && __align < sizeof(void *))
        __align = sizeof(void *);

    void* __mallocedMemory;
#if defined(__MINGW32__)
    __mallocedMemory = __mingw_aligned_malloc(__size, __align);
#elif defined(_WIN32)
    __mallocedMemory = _aligned_malloc(__size, __align);
#else
    if (posix_memalign(&__mallocedMemory, __align, __size)) {
        collector.copy(unit_log);
        return 0;
    }
#endif
    collector.copy(unit_log);

    return __mallocedMemory;
}
#endif

template <typename T, int line, char... filename>
void* malloc(size_t size, bool fakearg=true)
{
    string filestring = {filename...};

    unit_log.file = filetable.insert(filestring.c_str());
    unit_log.tindex_name = typetable.insert(typeid(T).name());

    void* ptr = memhook_malloc(size, unit_log.file, line, true);

    collector.copy(unit_log);
    return ptr;
}

#endif

uint64_t memhook_get_server_clock();

#define malloc(s) malloc_s((s), (__FILE__), (__LINE__))
#define free(s) free_s((s), (__FILE__), (__LINE__))
#endif //__MEMHOOK_INTERFACE_H