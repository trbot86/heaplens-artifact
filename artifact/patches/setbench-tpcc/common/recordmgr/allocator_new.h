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

// HeapLENS artifact addition: -DMEMHOOK_SEG_DS makes this allocator dlopen
// its OWN private instance of a malloc implementation (jemalloc by default,
// or mimalloc with -DUSE_MIMALLOC) and route every allocation of T through
// it, instead of through the process's normal `new`/`malloc`. Because each
// dlopen() of a shared malloc library gets its own independent set of
// arenas, this gives objects allocated via this allocator_new<T> a heap
// region that's disjoint from everything else the application allocates
// (including anything from the SAME malloc implementation reached via the
// process's normal allocation path, e.g. via LD_PRELOAD) -- reproducing the
// "separate memory arenas" / node-segregation fix described in the
// HeapLENS paper's Section 6.2 (ASCYLIB EFRB tree) and Section 6.3
// (TPC-C/BCCO and TPC-C/EFRB trees). See
// artifact/experiments/{ascylib_efrb_bench,tpcc_bcco_bench,tpcc_efrb_bench}.
//
// MEMHOOK_SEG_DS_LIB overrides the library path (must be resolvable via
// dlopen(), so either absolute or relative to the *process's* cwd at
// startup -- not to this header). The default matches where setbench's own
// vendored allocators live relative to macrobench/'s build output
// (setbench/lib/lib{jemalloc,mimalloc}.so), since these binaries are always
// run with macrobench/ as the working directory (see e.g.
// artifact/lib/tpcc_perfbench.sh).
#ifdef MEMHOOK_SEG_DS
#ifndef _GNU_SOURCE
#define _GNU_SOURCE // for dlmopen()/LM_ID_NEWLM
#endif
#include <dlfcn.h>

typedef void* (*malloc_fn_t)(size_t);
typedef void (*free_fn_t)(void*);

#ifndef MEMHOOK_SEG_DS_LIB
#ifdef USE_MIMALLOC
#define MEMHOOK_SEG_DS_LIB "../lib/libmimalloc.so"
#else
#define MEMHOOK_SEG_DS_LIB "../lib/libjemalloc.so"
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
        // HeapLENS artifact note: dlopen() here can fail with "cannot
        // allocate memory in static TLS block" whenever the library being
        // dlopen'd (or the process's own LD_PRELOAD'd allocator) uses
        // initial-exec TLS -- a well-known glibc limitation once the
        // process's static TLS surplus is exhausted, which is common with
        // modern jemalloc/mimalloc builds. dlmopen(LM_ID_NEWLM, ...) does
        // NOT fix this (initial-exec TLS is tied to the process's single
        // static TLS region regardless of link-map namespace) and further
        // exhausts glibc's small, fixed namespace limit (DL_NNS, typically
        // 16) since a fresh allocator_new<T> -- and therefore a fresh
        // dlopen -- is created per database table. The actual fix is to
        // give the *process* a bigger static TLS surplus up front via the
        // glibc.rtld.optional_static_tls tunable, e.g.:
        //   GLIBC_TUNABLES=glibc.rtld.optional_static_tls=4194304 ./rundb_...
        // (supported since glibc 2.35; see artifact/lib/tpcc_perfbench.sh,
        // which sets this for every run of these benchmarks).
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
        #endif
    }
    ~allocator_new() {
        VERBOSE DEBUG std::cout<<"destructor allocator_new"<<std::endl;
    }
};

#endif	/* ALLOC_NEW_H */
