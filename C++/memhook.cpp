#include "memhook.h"

void printstats() {
    for(int i = 0;i < it;i++) {
        cout << myArray[i];
    }
}

/**TODO:
 * Implement DMA operation to store info_t array into disk
 **/

void dumpstatstofile(const char* file) {

}

void printstacktrace(FILE* fd = stderr) {
    int nptrs;
    void* buffer[100];
    char** symbolists;

    nptrs = backtrace(buffer,100);
    
    #ifdef DEBUG
    printf("backtrace() returned %d addresses\n",nptrs);
    #endif

    //char** returned by backtrace_symbols must be free'd later
    symbolists = backtrace_symbols(buffer, nptrs);
    if(symbolists == NULL) {
        perror("backtrace_symbols");
        exit(EXIT_FAILURE);
    }

    char *begin_func = 0, *begin_offset = 0, *end_offset = 0, *demangled_name = NULL;
    //starting to parse the line to extract the mangled name and offset
    for(char* p = symbolists[BACKTRACE_DEPTH];*p;++p) {
        if(*p == '(') {
            begin_func = p;
        }
        else if(*p == '+') {
            begin_offset = p;
        }
        else if(*p == ')') {
            end_offset = p;
            break;
        }
    }

    #ifdef DEBUG
    printf("%s\n", symbolists[BACKTRACE_DEPTH]);
    #endif

    //Divide symbol string into separate strings
    if(begin_func && begin_offset && end_offset && begin_func < begin_offset) {
        *begin_func++ = '\0';
        *begin_offset++ = '\0';
        *end_offset = '\0';

        #ifdef DEBUG
        printf("%s %s\n", begin_func, begin_offset);
        #endif

        int status;
        demangled_name = abi::__cxa_demangle(begin_func, NULL, NULL, &status);

        switch(status) {
            case 0:
            #ifdef DEBUG
            printf("the demangling operation succeeded\n");
            #endif
            printf("%s\n", demangled_name);
            break;
            case -1:
            printf("memory allocation failure\n");
            break;
            case -2:
            printf("mangled_name is not a valid name under the C++ ABI mangling rules\n");
            break;
            case -3:
            printf("one of the arguments is invalid\n");
            break;
            default:
            printf("undefined_behaviour\n");
        }
    }
    else {
        printf("%s : %s()+%s\n",symbolists[BACKTRACE_DEPTH], begin_func, begin_offset);
    }
}

/**********************
 * 
 * Add bound checking for number of allocations
 * Do we need to initialize as zero first in order
 * to know when to stop while printing?
 * 
 **********************/
void * operator new(size_t size) {
    experimental::source_location loc = experimental::source_location::current();
    
    void* mem = malloc(size == 0?1:size);
    if(mem == 0) {
        throw bad_alloc();
    }

    info_t info = {
        loc.file_name(),
        loc.function_name(),
        type_index(),
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
    free(mem);
}