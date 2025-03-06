// mention Curtis Bartley
#ifndef __MEMHOOK_INTERFACE_H
#define __MEMHOOK_INTERFACE_H
#pragma once

// ASK ABOUT DIFFERENT IMPLEMENTATIONS OF BOOL IN C/C++. WILL THAT BE A PROBLEM?
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

#if defined(MEMHOOK_ASCYLIB)
#ifdef __cplusplus
extern "C" {
#endif
#include "memhook_ssmem.h"
#include "memhook_ssalloc.h"
#ifdef __cplusplus
}
#endif
#endif // MEMHOOK_ASCYLIB

#ifdef __cplusplus
#include <iostream>
#include <new>
#include <typeinfo>
#include <typeindex>
#include <bits/stdc++.h>
#include <sys/types.h>
#include <sys/stat.h>
// #include <fcntl.h>
#include <unistd.h>
#include <malloc.h>
#include <mm_malloc.h>
#include "memstamp.h"
#include "hash.h"


// #include "/root/teststatic/a.h"
// #include "mem_alloc.h"
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

#define MACRO_GET_128(str, i)      \
    MACRO_GET_64(str, i + 0),      \
        MACRO_GET_64(str, i + 64)

#define MACRO_GET_STR(str) MACRO_GET_128(str, 0), 0

#if defined(__cplusplus) && ! defined(MEMHOOK_C_LOG)
#define MEMHOOK_LOG_ALLOC(ptr, sz, tname) \
        unit_log.timestamp = memhook_get_server_clock(); \
        unit_log.size = sz; \
        unit_log.addr = ptr; \
        unit_log.typeofop = true; \
        unit_log.file = filetable.insert<MACRO_GET_STR(__FILE__)>(); \
        unit_log.tindex_name = typetable.insert(tname); \
        unit_log.line = __LINE__; \
        memhookCollector.copy(unit_log);
#else
#define MEMHOOK_LOG_ALLOC(ptr, sz, tname) \
        unit_log.timestamp = memhook_get_server_clock(); \
        unit_log.size = sz; \
        unit_log.addr = ptr; \
        unit_log.typeofop = true; \
        unit_log.file = filetable.insert(MACRO_GET_STR(__FILE__)); \
        unit_log.tindex_name = typetable.insert(tname); \
        unit_log.line = __LINE__; \
        memhookCollector.copy(unit_log);
#endif // __cplusplus

#define MEMHOOK_LOG_FREE(ptr) \
        unit_log.timestamp = memhook_get_server_clock(); \
        unit_log.addr = ptr; \
        unit_log.typeofop = false; \
        memhookCollector.copy(unit_log);

struct slot;
struct memhook_info_t;

uint64_t memhook_get_server_clock();

inline size_t memhook_roundUp(size_t size, size_t mult) {
    if (mult <= 1)
        return size;

    size_t rem = size % mult;
    return rem == 0 ? size : size + mult - rem;
}

// extern void* ssmem_alloc(ssmem_allocator_t* a, size_t size);
// extern void ssmem_free(ssmem_allocator_t* a, void* ptr);

#ifdef __cplusplus
extern "C"
{
#endif

    void* malloc_s(size_t, int, const char*, const char*, bool, void*);
    // void free_s(void *, int, const char*);
    void free_log(void*);
    #if defined(MEMHOOK_ASCYLIB)
    void* ssalloc_s(size_t, int, const char*, const char*);
    void* ssalloc_aligned_s(size_t, size_t, int, const char*, const char*);
    void* ssmem_alloc_s(ssmem_allocator_t*, size_t, int, const char*, const char*);
    #endif
    int posix_memalign_s(void**, size_t, size_t, int, const char*, const char*);
    void* memalign_s(size_t, size_t, int, const char*, const char*);
    void* calloc_s(size_t, size_t, int, const char*, const char*);
    #if defined(MEMHOOK_GZIP)
    void* xmalloc_s(size_t, int, const char*, const char*);
    void* xcalloc_s(size_t, size_t, int, const char*, const char*);
    #endif
    // void ssmem_free_s(ssmem_allocator_t*, void*, int, const char*);
    // void free(void* ptr);

    // void* ssalloc_alloc_s(unsigned int allocator, size_t size, const char* filepath, int line);
    // void* ssalloc_aligned_alloc_s(unsigned int allocator, size_t alignment, size_t size, const char* filepath, int line);
    // void ssfree_alloc_s(unsigned int allocator, void* ptr, const char* filepath, int line);

// #define SIFTER_NEW
// #define new MemStamp((__FILE__), (__LINE__)) * new
// #define delete MemStamp((__FILE__), (__LINE__)) * delete

#ifdef __cplusplus
}
#endif

#ifdef __cplusplus

extern MemStampCollector memhookCollector;
extern thread_local memhook_info_t unit_log;
// extern thread_local unordered_set<const char*> threadFiles;
// extern thread_local unordered_set<const char*> typeFiles;
extern memhook_hashtable filetable;
extern memhook_hashtable typetable;
extern void *memhook_malloc(size_t size, const char *file, int line, bool log);
extern void memhook_free(void *ptr, const char* file, int line, bool log);

// template <typename T>
// T malloc(size_t size, bool fakearg=true);

template <class T>
inline T* operator*(const MemStamp &stamp, T* p)
{
    //cout << "CALLED operator *" << endl;
    /************************************************/
    /* Rationale: placement new cannot be           */
    /* overloaded for now, hence timestamp is 0.    */
    /* If this is the case, then add timestamp here */
    /************************************************/
    if (unit_log.timestamp == 0)
        unit_log.timestamp = memhook_get_server_clock();
    // Following is a hack for placement new
    if (!unit_log.typeofop) {
        unit_log.size = sizeof(T);
        unit_log.addr = (void*) p;
        unit_log.typeofop = true;
    }
    unit_log.file = filetable.insert(stamp.filename);
    unit_log.line = stamp.lineNum;
    unit_log.tindex_name = typetable.insert(typeid(T).name());

    memhookCollector.copy(unit_log);
    return p;
}

#if defined(_mm_malloc)
template <typename T, int line, char... filename>
static __inline__ void* __attribute__((__always_inline__, __malloc__))
_mm_malloc(size_t __size, size_t __align)
{
    // string filestring = {filename...};

    unit_log.file = filetable.insert<filename...>();
    unit_log.tindex_name = typetable.insert(typeid(T).name());
    if (__align == 1)
    {
        void* ptr = memhook_malloc(__size, unit_log.file, line, true);
        memhookCollector.copy(unit_log);
        return ptr;
    }

    if (!(__align & (__align - 1)) && __align < sizeof(void *)) {
        __align = sizeof(void *);
    }

    void* __mallocedMemory;
#if defined(__MINGW32__)
    __mallocedMemory = __mingw_aligned_malloc(__size, __align);
#elif defined(_WIN32)
    __mallocedMemory = _aligned_malloc(__size, __align);
#else
    __mallocedMemory = _mm_malloc(__size, __align);
#endif
    unit_log.timestamp = memhook_get_server_clock();
    unit_log.size = memhook_roundUp(__size, __align);
    unit_log.addr = __mallocedMemory;
    unit_log.line = line;
    unit_log.typeofop = true;

    memhookCollector.copy(unit_log);

    return __mallocedMemory;
}
#endif

template <typename T, int line, char... filename>
int posix_memalign(void** ptr, size_t align, size_t size) {
    unit_log.file = filetable.insert<filename...>();
    unit_log.tindex_name = typetable.insert(typeid(T).name());
    unit_log.timestamp = memhook_get_server_clock();
    unit_log.size = memhook_roundUp(size, align);
    unit_log.line = line;
    unit_log.typeofop = true;

    int r = posix_memalign(ptr, align, size);
    unit_log.addr = *ptr;

    memhookCollector.copy(unit_log);

    return r;
}

template <typename T, int line, char... filename>
void* malloc(size_t size)
{
    unit_log.file = filetable.insert<filename...>();
    unit_log.tindex_name = typetable.insert(typeid(T).name());

    void* ptr = memhook_malloc(size, unit_log.file, line, true);

    memhookCollector.copy(unit_log);
    return ptr;
}

#endif // __cplusplus
#endif //__MEMHOOK_INTERFACE_H