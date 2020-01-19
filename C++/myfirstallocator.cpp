#include "myfirstallocator.h"

void printstats() {
    for(int i = 0;i < it;i++) {
        std::cout << myArray[i];
    }
}

void dumpstatstofile(const char* file) {

}

/**********************
 * 
 * Add bound checking for number of allocations
 * Do we need to initialize as zero first in order
 * to know when to stop while printing?
 * 
 **********************/
void * operator new(std::size_t size) {
    // if(!pthread_push_flag) {
    //     pthread_cleanup_push()
    // }

    std::experimental::source_location loc = std::experimental::source_location::current();
    
    void* mem = std::malloc(size == 0?1:size);
    if(mem == 0) {
        throw std::bad_alloc();
    }

    info_t info = {
        loc.file_name(),
        loc.function_name(),
        nullptr,
        loc.line(),
        get_server_clock(),
        size,
        mem,
    };

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
    myArray[it++] = info;  
    return mem;
}

void operator delete(void * mem) {

    /*
    *   Figure out how to elegantly call printstats (preferably with flags).
    *   For now, just calling printstats in delete
    * */
    printstats();
    std::free(mem);
}