// mention Curtis Bartley
#ifndef memhook_H_
#define memhook_H_

#include <iostream>
#include <new>
#include <typeinfo>
#include <typeindex>
#include <bits/stdc++.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <execinfo.h>
#include <cxxabi.h>

#define BACKTRACE_DEPTH 2
#define MAX_THREADS 1000
#define MAX_TRACK 1
#define MAX_TYPE_LENGTH 1000
#define PADDING 64

using namespace std;

class MemStamp
{
    public:
        char const * const filename;
        int const lineNum;
    public:
        MemStamp(char const *filename, int lineNum)
            : filename(filename), lineNum(lineNum) { }
        ~MemStamp() { }
};

struct info_t {
    const char* file;
    type_index tindex;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    char padding[PADDING];

    info_t() : file(nullptr), tindex(typeid(void)), line(0), timestamp(0), size(0), addr(nullptr) {}
};

void printstats();
void dumpfilemappingtofile(const char* file);
void dumpentirestatstofile(const char* file);
void dumpstatstofile(const char *file);
void insertType(void *p, const MemStamp &stamp, const type_index);
template <typename T> T malloc(size_t size);

template <class T>
inline T* operator * (const MemStamp &stamp, T *p) {
    insertType(p, stamp, type_index(typeid(T)));
    return p;
}

template <typename T>
T malloc(size_t size) {
    T ptr = (T)std::malloc(size);
    if(ptr == NULL) throw bad_alloc();

    return ptr;
}

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

/*Iterator for individual thread allocation in
* tracking data structure
*/
static thread_local int it = 0;

static thread_local bool pthread_push_flag;

//Keeps the total number of concurrent threads
static int arrayCount = 0;

typedef info_t** track_type;

typedef map<type_index, const char*> type_map;
typedef map<void*, string> filename_map;

static filename_map fmap;
static type_map tmap;

#define SIFTER_NEW MemStamp(__FILE__, __LINE__) * new
#define new SIFTER_NEW

#endif  