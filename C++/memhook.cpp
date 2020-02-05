#include "memhook.h"
#undef new

//Global array for tracking all allocations
info_t* allArrays[MAX_THREADS];

//Local array tracking a thread's allocations
thread_local info_t* myArray;

ostream& operator << (ostream& os, const info_t& info) {
        // os << *info.file << endl;
        // os << *info.function << endl;
        os << info.typeName << endl;
        os << info.line << endl;
        os << info.timestamp << endl;
        os << info.size << endl;
        os << info.addr << endl;
        return os;
}

void printstats() {
    for(int i = 0;i < it;i++) {
        cout << myArray[i];
    }
}

/***********************
 * Does periodic dumping of info_t structs to the disk
 * TODO:
 * Implement DMA operation to store info_t array into disk
 ***********************/

void dumpstatstofile(const char* file) {

}

void insertType(void *p, const MemStamp &stamp, const char *typeName) {
    myArray[it].file = stamp.filename;
    myArray[it].line = stamp.lineNum;
    myArray[it].typeName = typeName;
    it++;
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

    if(!myArray) {
        myArray = (info_t*)malloc(MAX_TRACK*sizeof(info_t));
        int result = __sync_fetch_and_add(&arrayCount,1);
        allArrays[result] = myArray;
    }

    /*ensure that number of allocations don't exceed the limit
    * make a policy for dumping the existing allocations before
    * reaching the limit
    **/

    assert(it < MAX_TRACK);
    myArray[it].timestamp = get_server_clock();
    myArray[it].size = size;
    myArray[it].addr = mem;

    return mem;
}

void *operator new[] (size_t size) {
    void* mem = malloc(size == 0?1:size);
    
    if(mem == 0) {
        throw bad_alloc();
    }

    if(!myArray) {
        myArray = (info_t*)malloc(MAX_TRACK*sizeof(info_t));
        int result = __sync_fetch_and_add(&arrayCount,1);
        allArrays[result] = myArray;
    }

    /*ensure that number of allocations don't exceed the limit
    * make a policy for dumping the existing allocations before
    * reaching the limit
    **/

    assert(it < MAX_TRACK);
    myArray[it].timestamp = get_server_clock();
    myArray[it].size = size;
    myArray[it].addr = mem;

    return mem;
}

void operator delete(void * mem) {

    /*
    *   Figure out how to elegantly call printstats (preferably with flags).
    *   For now, just calling printstats in delete
    * */
    printstats();
    free(mem);
}

void operator delete[](void *mem) {
    printstats();
    free(mem);
}