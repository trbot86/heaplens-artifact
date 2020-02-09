// mention Curtis Bartley
#ifndef memhook_H
#define memhook_H

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

/*Iterator for individual thread allocation in
* tracking data structure
*/
static thread_local int it = 0;

//Keeps the total number of concurrent threads
static int arrayCount = 0;

typedef info_t** track_type;

typedef map<type_index, const char*> type_map;

static type_map tmap;

//Global array for tracking all allocations
static info_t** allArrays;

//Local array tracking a thread's allocations
thread_local static info_t* myArray;

inline uint64_t get_server_clock();
void printstats();
void dumpentirestatstofile(const char* file);
void dumpstatstofile(const char *file);
void insertType(void *p, const MemStamp &stamp, const type_index);
void insert_info(size_t size, void* ptr, type_index tindex);
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

    insert_info(size, ptr, type_index(typeid(T)));

    return ptr;
}

#define SIFTER_NEW MemStamp(__FILE__, __LINE__) * new
#define new SIFTER_NEW

#endif  