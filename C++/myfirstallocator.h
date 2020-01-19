
#ifndef myfirstallocator
#define myfirst allocator

#include <iostream>
#include <bits/stdc++.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <experimental/source_location>

#define MAX_THREADS 1000
#define MAX_TRACK 1000

void printstats();
void dumpstatstofile(const char* file);
void* operator new (std::size_t);
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
    char* type;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
};

std::ostream& operator << (std::ostream& os, const info_t& info) {
        // os << *info.file << std::endl;
        // os << *info.function << std::endl;
        // os << *info.type << std::endl;
        os << info.line << std::endl;
        os << info.timestamp << std::endl;
        os << info.size << std::endl;
        os << info.addr << std::endl;
        return os;
    }

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
struct internalalloc: std::allocator<T> {
    typedef typename std::allocator<T>::pointer pointer;
    typedef typename std::allocator<T>::size_type size_type;

    template<typename U>
    struct rebind {
        typedef internalalloc<U> other;
    };

    //STANDARD CONSTRUCTOR
    internalalloc() {}

    //TEMPLATIZED COPY CONSTRUCTOR
    template<typename U>
    internalalloc(internalalloc<U> const& u): std::allocator<T>(u) {}

    pointer allocate(size_type size, std::allocator<void>::const_pointer = 0) {
        void* ptr = malloc(size*sizeof(T));
        if(ptr == 0) {
            throw std::bad_alloc();
        }
        return static_cast<pointer>(ptr);
    }

    void deallocate(pointer p, size_type) {
        std::free(p);
    }
};

typedef info_t** track_type;
#endif