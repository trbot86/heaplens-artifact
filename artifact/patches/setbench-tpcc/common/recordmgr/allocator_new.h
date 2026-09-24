/**
 * C++ record manager implementation (PODC 2015) by Trevor Brown.
 *
 * Copyright (C) 2015 Trevor Brown
 *
 */

#ifndef ALLOC_NEW_H
#define	ALLOC_NEW_H

#include "plaf.h"
#include "pool_interface.h"
#include <cstdlib>
#include <cassert>
#include <iostream>

// MEMHOOK_SEG_DS routes record-managed tree objects through a separately
// loaded allocator rather than the process-wide allocation path. The TPC-C
// drivers stage the retained jemalloc library under a distinct filename.
// Repeated dlopen calls for that file SHARE one instance across tables/types;
// reopening the process-wide library would NOT create a separate instance.
// This implements tree-vs-database segregation, not a private heap per table.
//
// MEMHOOK_SEG_DS_LIB overrides the library path (must be resolvable via
// dlopen(), so either absolute or relative to the *process's* cwd at
// startup -- not to this header). The default jemalloc file is staged in the
// source copy's lib/ directory, with macrobench/ as the working directory.
// The optional USE_MIMALLOC path must also differ from the global allocator;
// the paper's configurations do not use that selector.
#ifdef MEMHOOK_SEG_DS
#ifndef _GNU_SOURCE
#define _GNU_SOURCE // for RTLD_DEFAULT
#endif
#include <dlfcn.h>

typedef void* (*malloc_fn_t)(size_t);
typedef void (*free_fn_t)(void*);

#ifndef MEMHOOK_SEG_DS_LIB
#ifdef USE_MIMALLOC
#define MEMHOOK_SEG_DS_LIB "../lib/libmimalloc.so"
#else
#define MEMHOOK_SEG_DS_LIB "../lib/libjemalloc-heaplens.so"
#endif
#endif
#endif

//__thread long long currentAllocatedBytes = 0;
//__thread long long maxAllocatedBytes = 0;

template<typename T = void>
class allocator_new : public allocator_interface<T> {
    #ifdef MEMHOOK_SEG_DS
    malloc_fn_t ds_malloc;
    free_fn_t ds_free;
    #endif
    PAD; // post padding for allocator_interface
public:
    template<typename _Tp1>
    struct rebind {
        typedef allocator_new<_Tp1> other;
    };

    // reserve space for ONE object of type T
    T* allocate(const int tid) {
        // allocate a new object
        MEMORY_STATS {
            this->debug->addAllocated(tid, 1);
            VERBOSE {
                if ((this->debug->getAllocated(tid) % 2000) == 0) {
                    debugPrintStatus(tid);
                }
            }
//            currentAllocatedBytes += sizeof(T);
//            if (currentAllocatedBytes > maxAllocatedBytes) {
//                maxAllocatedBytes = currentAllocatedBytes;
//            }
        }
        #ifdef MEMHOOK_SEG_DS
        return (T*) ds_malloc(sizeof(T));
        #else
        return new T; //(T*) malloc(sizeof(T));
        #endif
    }
    void deallocate(const int tid, T * const p) {
        // note: allocators perform the actual freeing/deleting, since
        // only they know how memory was allocated.
        // pools simply call deallocate() to request that it is freed.
        // allocators do not invoke pool functions.
        MEMORY_STATS {
            this->debug->addDeallocated(tid, 1);
//            currentAllocatedBytes -= sizeof(T);
        }
#if !defined NO_FREE
#if defined TIMELINE_RECORD_EVERY_DEAMORTIZED_FREE
        TIMELINE_START(tid);
#endif
        #ifdef MEMHOOK_SEG_DS
        ds_free(p);
        #else
        delete p;
        #endif
#if defined TIMELINE_RECORD_EVERY_DEAMORTIZED_FREE
        TIMELINE_END_INMEM_Llu(tid, timeline_freeOne, 0);
#endif
#endif
    }
    void deallocateAndClear(const int tid, blockbag<T> * const bag) {
#ifdef NO_FREE
        bag->clearWithoutFreeingElements();
#else
        // int i=0;
        while (!bag->isEmpty()) {
            T* ptr = bag->remove();
// #if !defined DEAMORTIZE_FREE_CALLS && defined TIMELINE_RECORD_EVERY_DEAMORTIZED_FREE
//             TIMELINE_START(tid);
//             ++i;
// #endif
            deallocate(tid, ptr);
// #if !defined DEAMORTIZE_FREE_CALLS && defined TIMELINE_RECORD_EVERY_DEAMORTIZED_FREE
//             TIMELINE_END_INMEM_Llu(tid, timeline_freeOne, i);
// #endif
        }
#endif
    }

    void debugPrintStatus(const int tid) {
//        std::cout<</*"thread "<<tid<<" "<<*/"allocated "<<this->debug->getAllocated(tid)<<" objects of size "<<(sizeof(T));
//        std::cout<<" ";
////        this->pool->debugPrintStatus(tid);
//        std::cout<<std::endl;
    }

    void initThread(const int tid) {}
    void deinitThread(const int tid) {}

    allocator_new(const int numProcesses, debugInfo * const _debug)
            : allocator_interface<T>(numProcesses, _debug) {
        VERBOSE DEBUG std::cout<<"constructor allocator_new"<<std::endl;
        #ifdef MEMHOOK_SEG_DS
        // A distinct allocator using initial-exec TLS may need additional
        // static-TLS space. The performance driver sets GLIBC_TUNABLES before
        // startup. Loading the same file repeatedly does not create new heaps.
        void* malloc_copy = dlopen(MEMHOOK_SEG_DS_LIB, RTLD_LAZY);
        if (!malloc_copy) {
            std::cout << "ERROR: failed to dlopen malloc library " << MEMHOOK_SEG_DS_LIB << std::endl;
            std::cout << dlerror() << std::endl;
            exit(-1);
        }
        ds_malloc = (malloc_fn_t) dlsym(malloc_copy, "malloc");
        ds_free = (free_fn_t) dlsym(malloc_copy, "free");

        if (!ds_malloc) {
            std::cout << "ERROR: failed to resolve malloc" << std::endl;
            exit(-1);
        }
        else if (!ds_free) {
            std::cout << "ERROR: failed to resolve free" << std::endl;
            exit(-1);
        }
        if (reinterpret_cast<void*>(ds_malloc) == dlsym(RTLD_DEFAULT, "malloc")) {
            std::cerr << "ERROR: MEMHOOK_SEG_DS resolved to the process-wide allocator; "
                      << "use the separately staged HeapLENS allocator library." << std::endl;
            exit(-1);
        }
        #endif
    }
    ~allocator_new() {
        VERBOSE DEBUG std::cout<<"destructor allocator_new"<<std::endl;
    }
};

#endif	/* ALLOC_NEW_H */
