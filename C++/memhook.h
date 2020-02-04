
#ifndef memhook
#define memhook

#include <iostream>
#include <typeinfo>
#include <typeindex>
#include <bits/stdc++.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <execinfo.h>
#include <cxxabi.h>
#include <experimental/source_location>

#define BACKTRACE_DEPTH 2
#define MAX_THREADS 1000
#define MAX_TRACK 1000
#define MAX_TYPE_LENGTH 1000

using namespace std;

void printstats();
void dumpstatstofile(const char* file);
void* operator new (size_t);
void operator delete (void* ptr);

inline uint64_t get_server_clock() {
#if defined(__i386__)
    uint64_t ret;
    __asm__ __volatile__("rdtsc" : "=A" (ret));
#elif defined(__x86_64__)
    unsigned hi, lo;
    __asm__ __volatile__ ("rdtsc" : "=a"(lo), "=d"(hi));
    uint64_t ret = ( (uint64_t)lo)|( ((uint64_t)hi)<<32 );
#else 
    #error Must support RDTSC instruction! Sorry...
#endif
    return ret;
}

//COMPRESS THE DATA STRUCTURE
struct info_t {
    const char* file;
    const char* function;
    const type_index tindex;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
};

ostream& operator << (ostream& os, const info_t& info) {
        // os << *info.file << endl;
        // os << *info.function << endl;
        os << type_names[info.tindex] << endl;
        os << info.line << endl;
        os << info.timestamp << endl;
        os << info.size << endl;
        os << info.addr << endl;
        return os;
    }

//Global map for storing type_index to type name string information
unordered_map<type_index, string> type_names;

//Global array for tracking all allocations
info_t* allArrays[MAX_THREADS];

//Local array tracking a thread's allocations
thread_local info_t* myArray;

/*Iterator for individual thread allocation in
* tracking data structure
*/
static thread_local int it = 0;

static thread_local bool pthread_push_flag;

//Keeps the total number of concurrent threads
static int arrayCount = 0;

template<typename T>
struct internalalloc: allocator<T> {
    typedef typename allocator<T>::pointer pointer;
    typedef typename allocator<T>::size_type size_type;

    template<typename U>
    struct rebind {
        typedef internalalloc<U> other;
    };

    //STANDARD CONSTRUCTOR
    internalalloc() {}

    //TEMPLATIZED COPY CONSTRUCTOR
    template<typename U>
    internalalloc(internalalloc<U> const& u): allocator<T>(u) {}

    pointer allocate(size_type size, allocator<void>::const_pointer = 0) {
        void* ptr = malloc(size*sizeof(T));
        if(ptr == 0) {
            throw bad_alloc();
        }
        return static_cast<pointer>(ptr);
    }

    void deallocate(pointer p, size_type) {
        free(p);
    }
};

typedef info_t** track_type;
#endif