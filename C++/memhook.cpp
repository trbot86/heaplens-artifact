#include "memhook.h"
#undef new

//Global array for tracking all allocations
info_t allArrays[MAX_THREADS][MAX_TRACK];

//Local array tracking a thread's allocations
thread_local info_t* myArray = nullptr;

ostream& operator << (ostream& os, info_t& info) {
        os << info.file << endl;
        os << info.tindex.name() << endl;
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
 * Does periodic dumping of info_t structs to the disk.
 * 
 * 1) First demangle all the type names and store them in the type_name map
 * 2) Store the info_t struct with the type name in disk
 * TODO:
 * Implement DMA operation to store info_t array into disk
 ***********************/

void dumpfilemappingtofile(const char* file) {
    ofstream myfile(file, ios_base::out | ios_base::app);

    for(filename_map::iterator it = fmap.begin();it != fmap.end(); ++it) {
        myfile << (*it).first;
        myfile << (*it).second;
        cout << (*it).first;
    }
}

void dumpentirestatstofile(const char* file) {
    for(int j = 0;j <= arrayCount;j++) {
    for(int i = 0;i < MAX_TRACK;i++) {
        if(!fmap.count((void*)allArrays[j][i].file) && allArrays[j][i].file) {
            fmap[(void*)allArrays[j][i].file] = string(allArrays[j][i].file);
        }
    }
    }

    ofstream myfile(file, ios_base::out | ios_base::app);
    
    for(int i = 0;i < arrayCount;i++) {
        myfile.write(reinterpret_cast<char*>(allArrays[i]), MAX_TRACK*sizeof(info_t));
    }
}

void dumpstatstofile(const char* file) {
    for(int i = 0;i < it;i++) {
        if(!fmap.count((void*)myArray[i].file)) {
            fmap[(void*)myArray[i].file] = *myArray[i].file;
        }
    }

    ofstream myfile (file, ios_base::out | ios_base::app);
    myfile.write(reinterpret_cast<char*>(myArray), MAX_TRACK*sizeof(info_t));
}

void insertType(void *p, const MemStamp &stamp,const type_index tindex) {
    myArray[it].file = stamp.filename;
    myArray[it].line = stamp.lineNum;
    myArray[it].tindex = tindex;
    
    it = (it+1)%MAX_TRACK;
    
    // if(!it) {
    //     dumpstatstofile("info_t_dump.txt");
    // }
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
        int result = __sync_fetch_and_add(&arrayCount,1);
        myArray = allArrays[result];
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
        int result = __sync_fetch_and_add(&arrayCount,1);
        myArray = allArrays[result];
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
    free(mem);
}

void operator delete[](void *mem) {
    free(mem);
}