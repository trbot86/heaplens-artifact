// #pragma once
/**
 * List of functions to overload obtained from mimalloc:
 *      https://github.com/microsoft/mimalloc/blob/master/src/alloc-override.c
 *
 * Simple tmpbuff allocator to avoid bad LD_PRELOAD interaction with DLSYM init adapted from:
 *      https://stackoverflow.com/questions/6083337/overriding-malloc-using-the-ld-preload-mechanism
 *
 * Caveat: until init() is complete, malloc should only be called by a single thread (in dl_init()).
 *         (This should essentially always be true...)
 */
#if defined(_WIN32) || defined(__APPLE__) || defined(__ANDROID__)
#error "Currently we do not support Windows, Apple, Android"
#endif

#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include <dlfcn.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include "memhook_interface.h"
#include "memhook.h"

#undef new

#ifndef mallog_likely
    #if defined(__GNUC__) || defined(__clang__)
        #define mallog_unlikely(x)     __builtin_expect((x),0)
        #define mallog_likely(x)       __builtin_expect((x),1)
    #else
        #define mallog_unlikely(x)     (x)
        #define mallog_likely(x)       (x)
    #endif
#endif

static char tmpbuff[1<<20];
static unsigned long tmppos = 0;
static unsigned long tmpallocs = 0;
// void *memset(void*, int, size_t);
// void *memmove(void *to, const void *from, size_t size);
// ------------------------------------------------------
// Override system malloc
// ------------------------------------------------------

// static void * (*next_valloc)(size_t size) = 0;
// static void * (*next_pvalloc)(size_t size) = 0;
// static void * (*next_memalign)(size_t blocksize, size_t bytes) = 0;
// static int    (*next_posix_memalign)(void **memptr, size_t alignment, size_t size) = 0;
// static void * (*next_aligned_alloc)(size_t alignment, size_t size) = 0;
// static void * (*next_realloc)(void *ptr, size_t size) = 0;
// static void * (*next_reallocf)(void *ptr, size_t size) = 0;
// static void * (*next_reallocarray)(void *ptr, size_t nmemb, size_t size) = 0;

static volatile int initialized = 0;

__attribute__((constructor)) static void init() {
    fprintf(stdout, "loading rtld_next functions...\n");
    next_malloc         = (void * (*)(size_t ))dlsym(RTLD_NEXT, "malloc");
    if (!next_malloc) exit(43);
    // fprintf(stdout, "    malloc\n");
    fprintf(stdout, "    next_malloc@%p \n", next_malloc);
    next_free           = (void   (*)(void *))dlsym(RTLD_NEXT, "free");
    fprintf(stdout, "    free\n");
    next_calloc         = (void * (*)(size_t , size_t ))dlsym(RTLD_NEXT, "calloc");
    fprintf(stdout, "    calloc\n");
    // next_valloc         = dlsym(RTLD_NEXT, "valloc");
    // fprintf(stdout, "    valloc\n");
    // next_pvalloc        = dlsym(RTLD_NEXT, "pvalloc");
    // fprintf(stdout, "    pvalloc\n");
    // next_memalign       = dlsym(RTLD_NEXT, "memalign");
    // fprintf(stdout, "    memalign\n");
    // next_posix_memalign = dlsym(RTLD_NEXT, "posix_memalign");
    // fprintf(stdout, "    posix_memalign\n");
    // next_aligned_alloc  = dlsym(RTLD_NEXT, "aligned_alloc");
    // fprintf(stdout, "    aligned_alloc\n");
    // next_realloc        = dlsym(RTLD_NEXT, "realloc");
    // fprintf(stdout, "    realloc\n");
    // next_reallocf       = dlsym(RTLD_NEXT, "reallocf");
    // fprintf(stdout, "    reallocf\n");
    // next_reallocarray   = dlsym(RTLD_NEXT, "reallocarray");
    // fprintf(stdout, "    reallocarray\n");
    fprintf(stdout, "    done.\n");
    initialized = 1;
    if (!next_malloc || !next_free) {
        fprintf(stderr, "Error in `dlsym`: %s\n", dlerror());
        exit(1);
    }
}

void *memhook_malloc(size_t size, char* file, int line, bool log) {
    if (!initialized) {
        if (tmppos + size < sizeof(tmpbuff)) {
            void *retptr = tmpbuff + tmppos;
            tmppos += size;
            ++tmpallocs;
            if (!retptr) exit(72);
            return retptr;
        } else {
            // fprintf(stdout, "jcheck: too much memory requested during initialisation - increase tmpbuff size\n");
            exit(99);
        }
    }

    if(!setup) {
        exiter.add();
        setup = true;
    }

    if (next_malloc == 0) exit(42);
    void * mem = next_malloc(size);

    // if (!mem) exit(71);

    if(mem == 0) {
        throw bad_alloc();
    }

    collector.add(memhook_get_server_clock(), size, mem, true);
    collector.update(file, line, NULL);

    // printf("real malloc called!\n");
    return mem;
}

void memhook_free(void *ptr, bool log) {
    // // something wrong if we call free before one of the allocators!
    // if (mallog_unlikely(next_malloc == 0)) {
    //     fprintf(stdout, "Free called before first allocation!\n");
    // }
    if(!setup) {
        exiter.add();
        setup = true;
    }
    
    if ((ptr >= (void*) tmpbuff && ptr <= (void*)(tmpbuff + tmppos))) { // possible off-by-one error at right endpoint...
        fprintf(stdout, "freeing temp memory\n");
    } else {
        next_free(ptr);
        collector.add(memhook_get_server_clock(), 0, ptr, false);
    }
}
// void *realloc(void *ptr, size_t size) {
// //     // if (mallog_unlikely(next_malloc == 0)) {
// //     //     void *nptr = malloc(size);
// //     //     if (nptr && ptr) {
// //     //         memmove(nptr, ptr, size);
// //     //         free(ptr);
// //     //     }
// //     //     return nptr;
// //     // }
//     return next_realloc(ptr, size);
// }
void *memhook_calloc(size_t nmemb, size_t size, char* file, int line, bool log) {
        if ((!initialized)) {
        // printf("nmemb*size=%lu\n", (nmemb*size));
        void *ptr = memhook_malloc(nmemb*size, file, line, false);
        // printf("nmemb*size=%lu\n", (nmemb*size));
        if (ptr) memset(ptr, 0, nmemb*size);
        if (!ptr) exit(70);
        return ptr;
    }
    return next_calloc(nmemb, size);
}

extern "C" {

    void *malloc_s(size_t size, char* filepath, int line) {
        printf("%s", filepath);
        return memhook_malloc(size, filepath, line, true);
    }


    void free(void *ptr) {
        return memhook_free(ptr, true);
    }

    // void *calloc(size_t nmemb, size_t size) {
    //     return memhook_calloc(nmemb, size, true);
    // }
}

ostream& operator << (ostream& os, info_t& info) {
        if(info.file) {
            os << info.file << "|" << tmap[info.tindex.name()] << "|" << info.line << "|" << info.timestamp << "|" << info.size << "|" << (long)info.addr << "|" << info.typeofop << endl;
        }
        else {
            os << "empty" << "|" << "emptytype" << "|" << info.line << "|" << info.timestamp << "|" << 0 << "|" << (long)info.addr << "|" << info.typeofop << endl;
        }
        return os;
}

void printstats() {
    for(int i = 0;i < it;i++) {
        cout << myArray[i];
    }
}

/***********************
 * Does periodic dumping of info_t structs to the disk.
 * 
 * 1) First demangle all the type names and store them in the type_name map
 * 2) Store the info_t struct with the type name in disk
 * TODO:
 * Implement DMA operation to store info_t array into disk
 ***********************/

// void dumpentirestatstofile() {
//     ofstream myfile("info_t_dump.txt", ios_base::out | ios_base::app);
//     ofstream filemap("filemap", ios_base::out | ios_base::app);
//     ofstream typemap("typemap", ios_base::out | ios_base::app);

//     int status;
//     char* demangled_name;

//     for(int i = 0;i < MAX_TRACK*MAX_THREADS;i++) {
//         while(allArrays[i].addr == nullptr) i++;
        
//         if(allArrays[i].file && allArrays[i].typeofop && !tmap.count(allArrays[i].tindex)) {
//             demangled_name = abi::__cxa_demangle(allArrays[i].tindex.name(), 0, 0, &status);
//             tmap[allArrays[i].tindex] = demangled_name;
//         }

//         if(allArrays[i].file && !fset.count(allArrays[i].file)) {
//             fset.insert(allArrays[i].file);
//         }
//     }

//     for(auto i = fset.begin();i != fset.end();i++) {
//         filemap.write(*i, sizeof(char*));
//         filemap.write(*i, sizeof(*i));
//     }

//     for(auto i = tmap.begin();i != tmap.end();i++) {
//         typemap.write((char*)&(*i).first, sizeof(type_index));
//         typemap.write((*i).second, sizeof((*i).second));
//     }

//     myfile.write(reinterpret_cast<char const*>(allArrays), MAX_THREADS*MAX_TRACK*sizeof(info_t));
// }

// void dumpentirestatstofile2() {
//     it = INT_MAX;
//     ofstream myfile("info_t_dump.txt", ios_base::out | ios_base::app);

//     int status;
//     char* demangled_name;

//     for(int i = 0;i < MAX_TRACK*MAX_THREADS;i++) {
//         if(allArrays[i].addr == nullptr) continue;
//         else if(allArrays[i].file && allArrays[i].typeofop && !tmap.count(allArrays[i].tindex)) {
//             demangled_name = abi::__cxa_demangle(allArrays[i].tindex.name(), 0, 0, &status);
//             tmap[allArrays[i].tindex] = demangled_name;
//         }

//         myfile << allArrays[i];
//     }
// }

// void dumpstatstofile(const char* file) {
//     for(int i = 0;i < MAX_TRACK;i++) {
//         if(!tmap.count(myArray[i].tindex)) {
//             tmap[myArray[i].tindex] = myArray[i].tindex.name();
//         }
//     }

//     ofstream myfile (file, ios_base::out | ios_base::app);
//     for(int i = 0;i < MAX_TRACK;i++) {
//         myfile << myArray[i];
//     }
// }

/**********************
 * TODO:
 * Add bound checking for number of allocations
 * Do we need to initialize as zero first in order
 * to know when to stop while printing?
 * 
 **********************/
void * operator new(size_t size) {

    void* mem = memhook_malloc(size == 0?1:size, NULL, 0, true);

    if(mem == 0) {
        throw bad_alloc();
    }

    return mem;
}

void *operator new[] (size_t size) {

    void* mem = memhook_malloc(size == 0?1:size, NULL, 0, true);
    
    if(mem == 0) {
        throw bad_alloc();
    }

    return mem;
}

void operator delete(void * mem)  _GLIBCXX_USE_NOEXCEPT {
    return memhook_free(mem, true);
}

void operator delete[](void *mem)  _GLIBCXX_USE_NOEXCEPT {
    return memhook_free(mem, true);
}
