// mention Curtis Bartley
#ifndef __MEMHOOK_INTERFACE_H
#define __MEMHOOK_INTERFACE_H
#pragma once

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
#include <unistd.h>
#include <malloc.h>
#include <mm_malloc.h>
#include "memstamp.h"
#include "hash.h"


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

#define MEMHOOK_LOG_CPP_ALLOC(ptr, sz, tid) \
        unit_log.timestamp = memhook_get_server_clock(); \
        unit_log.size = sz; \
        unit_log.addr = ptr; \
        unit_log.typeofop = true; \
        unit_log.tindex_name = typetable.insert(&tid); \
        unit_log.line = __LINE__; \
        memhookCollector.copy(unit_log);

#define MEMHOOK_LOG_C_ALLOC(ptr, sz, line, fname, tid) \
        unit_log.timestamp = memhook_get_server_clock(); \
        unit_log.size = sz; \
        unit_log.addr = ptr; \
        unit_log.typeofop = true; \
        unit_log.file = fname; \
        unit_log.tindex_name = tid; \
        unit_log.line = line; \
        memhookCollector.copy(unit_log);


#define MEMHOOK_LOG_FREE(ptr) \
        unit_log.timestamp = memhook_get_server_clock(); \
        unit_log.addr = ptr; \
        unit_log.typeofop = false; \
        memhookCollector.copy(unit_log);


struct slot;
struct memhook_info_t;

uint64_t memhook_get_server_clock();

inline size_t memhook_round_up(size_t size, size_t mult) {
    if (mult <= 1)
        return size;

    size_t rem = size % mult;
    return rem == 0 ? size : size + mult - rem;
}

#ifdef __cplusplus
extern "C" {
#endif

    void* malloc_s(size_t, int, uint16_t, uint16_t);
    #if defined(MEMHOOK_ASCYLIB)
    void* ssalloc_s(size_t, int, uint16_t, uint16_t);
    void* ssalloc_aligned_s(size_t, size_t, int, uint16_t, uint16_t);
    void* ssmem_alloc_s(ssmem_allocator_t*, size_t, int, uint16_t, uint16_t);
    #endif
    int posix_memalign_s(void**, size_t, size_t, int, uint16_t, uint16_t);
    void* memalign_s(size_t, size_t, int, uint16_t, uint16_t);
    void* calloc_s(size_t, size_t, int, uint16_t, uint16_t);
    #if defined(MEMHOOK_GZIP)
    void* xmalloc_s(size_t, int, uint16_t, uint16_t);
    void* xcalloc_s(size_t, size_t, int, uint16_t, uint16_t);
    #endif
#ifdef __cplusplus
}
#endif

#ifdef __cplusplus

extern MemStampCollector memhookCollector;
extern thread_local memhook_info_t unit_log;
extern memhook_hashtable filetable;
extern memhook_hashtable typetable;
extern void *memhook_malloc(size_t size, int line, bool log);
extern void memhook_free(void *ptr, int line, bool log);


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
    // unit_log.file = filetable.insert(stamp.filename);
    unit_log.file = stamp.filename;
    unit_log.line = stamp.lineNum;
    unit_log.tindex_name = typetable.insert(&typeid(T));

    memhookCollector.copy(unit_log);
    return p;
}

template <typename T, int line, uint16_t filename>
static __inline__ void* __attribute__((__always_inline__, __malloc__))
_mm_malloc(size_t __size, size_t __align) {
    unit_log.file = filename;
    unit_log.tindex_name = typetable.insert(&typeid(T));
    if (__align == 1) {
        void* ptr = memhook_malloc(__size, line, true);
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
    unit_log.size = __size;
    unit_log.addr = __mallocedMemory;
    unit_log.line = line;
    unit_log.typeofop = true;

    memhookCollector.copy(unit_log);

    return __mallocedMemory;
}

template <typename T, int line, uint16_t filename>
int posix_memalign(void** ptr, size_t align, size_t size) {
    unit_log.file = filename;
    unit_log.tindex_name = typetable.insert(&typeid(T));
    unit_log.timestamp = memhook_get_server_clock();
    unit_log.size = size;
    unit_log.line = line;
    unit_log.typeofop = true;

    int r = posix_memalign(ptr, align, size);
    if (r == 0 && *ptr) {
        unit_log.addr = *ptr;
        memhookCollector.copy(unit_log);
    }

    return r;
}

template <typename T, int line, uint16_t filename>
void* malloc(size_t size) {
    unit_log.file = filename;
    unit_log.tindex_name = typetable.insert(&typeid(T));

    void* ptr = memhook_malloc(size, line, true);

    memhookCollector.copy(unit_log);
    return ptr;
}

#endif // __cplusplus
#endif //__MEMHOOK_INTERFACE_H
