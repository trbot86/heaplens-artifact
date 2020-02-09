#include "memhook.h"
#undef new

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

ostream& operator << (ostream& os, info_t& info) {
        os << info.file << endl;
        os << tmap[info.tindex] << endl;
        os << info.line << endl;
        os << info.timestamp << endl;
        os << info.size << endl;
        os << info.addr << endl;
        // os << pthread_self() << endl;
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

void dumpentirestatstofile(const char* file) {
    ofstream myfile(file, ios_base::out | ios_base::app);
    int j = 0, status;
    char* demangled_name;

    for(int i = 0;i <= arrayCount;i++) {
        j = 0;
        while(allArrays[i][j].addr != nullptr) {
            if(!tmap.count(allArrays[i][j].tindex)) {
                demangled_name = abi::__cxa_demangle(allArrays[i][j].tindex.name(), 0, 0, &status);
                tmap[allArrays[i][j].tindex] = demangled_name;
            }

            myfile << allArrays[i][j];
            j++;
        }
    }
}

void dumpstatstofile(const char* file) {
    for(int i = 0;i < MAX_TRACK;i++) {
        if(!tmap.count(myArray[i].tindex)) {
            tmap[myArray[i].tindex] = myArray[i].tindex.name();
        }
    }

    ofstream myfile (file, ios_base::out | ios_base::app);
    for(int i = 0;i < MAX_TRACK;i++) {
        myfile << myArray[i];
    }
}

void insertType(void *p, const MemStamp &stamp,const type_index tindex) {
    if(it < MAX_TRACK) {
        myArray[it].file = stamp.filename;
        myArray[it].line = stamp.lineNum;
        myArray[it].tindex = tindex;
        it++;
    }

    // it = (it+1)%MAX_TRACK;
    
    // if(!it) {
    //     dumpstatstofile("info_t_dump.txt");
    // }
}

void insert_info(size_t size, void* ptr, type_index tindex) {
    if(!allArrays) {
        allArrays = (info_t**)malloc(MAX_THREADS*sizeof(info_t*));
        for(int i = 0;i < MAX_THREADS;i++) {
            allArrays[i] = (info_t*)malloc(MAX_TRACK*sizeof(info_t));
        }
    }

    if(!myArray) {
        int result = __sync_fetch_and_add(&arrayCount,1);
        myArray = allArrays[result];
    }
    
    if(it < MAX_TRACK) {
        myArray[it].tindex = tindex;
        myArray[it].timestamp = get_server_clock();
        myArray[it].size = size;
        myArray[it].addr = ptr;
    }
}

/**********************
 * TODO:
 * Add bound checking for number of allocations
 * Do we need to initialize as zero first in order
 * to know when to stop while printing?
 * 
 **********************/
void * operator new(size_t size) {
    
    void* mem = malloc(size == 0?1:size);
    
    if(mem == 0) {
        throw bad_alloc();
    }

    if(!allArrays) {
        allArrays = (info_t**)malloc(MAX_THREADS*sizeof(info_t*));
        for(int i = 0;i < MAX_THREADS;i++) {
            allArrays[i] = (info_t*)malloc(MAX_TRACK*sizeof(info_t));
        }
    }

    if(!myArray) {
        int result = __sync_fetch_and_add(&arrayCount,1);
        myArray = allArrays[result];
    }

    /*ensure that number of allocations don't exceed the limit
    * make a policy for dumping the existing allocations before
    * reaching the limit
    **/

    if(it < MAX_TRACK) {
        myArray[it].timestamp = get_server_clock();
        myArray[it].size = size;
        myArray[it].addr = mem;
    }

    return mem;
}

void *operator new[] (size_t size) {
    void* mem = malloc(size == 0?1:size);
    
    if(mem == 0) {
        throw bad_alloc();
    }

    if(!allArrays) {
        allArrays = (info_t**)malloc(MAX_THREADS*sizeof(info_t*));
        for(int i = 0;i < MAX_THREADS;i++) {
            allArrays[i] = (info_t*)malloc(MAX_TRACK*sizeof(info_t));
        }
    }

    if(!myArray) {
        int result = __sync_fetch_and_add(&arrayCount,1);
        myArray = allArrays[result];
    }

    /*ensure that number of allocations don't exceed the limit
    * make a policy for dumping the existing allocations before
    * reaching the limit
    **/

    if(it < MAX_TRACK) {
        myArray[it].timestamp = get_server_clock();
        myArray[it].size = size;
        myArray[it].addr = mem;
    }

    return mem;
}

void operator delete(void * mem) {
    free(mem);
}

void operator delete[](void *mem) {
    free(mem);
}