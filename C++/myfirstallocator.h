#include <iostream>
#include <bits/stdc++.h>
#include <experimental/source_location>

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

struct info_t {
    const char* file;
    const char* function;
    char* type;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
};

template<typename T>
struct internalalloc: std::allocator<T> {
    typedef typename std::allocator<T>::pointer pointer;
    typedef typename std::allocator<T>::size_type size_type;

    //ASK THE USE OF THIS
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

typedef std::map<void*, info_t, std::less<void*>, internalalloc<std::pair<void* const, info_t>> > track_type;