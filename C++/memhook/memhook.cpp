#include "memhook.h"
#undef new
#undef malloc

slot *sarr = nullptr;

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

void allocArray() {
    allArrays = (info_t*)malloc(MAX_THREADS*MAX_TRACK*sizeof(info_t));
    sarr = (slot*)malloc(MAX_THREADS*sizeof(slot));
}

int get_slot(thread::id id) {
	while(true) {
		while(sarr[iter].occupied) {
			// cout << "while" << endl;
			iter = (iter+1)%MAX_THREADS;
		}
		
		if(__sync_bool_compare_and_swap(&sarr[iter].occupied, false, true)) {
			cout << iter << endl;
			sarr[iter].id = id;
            it = sarr[iter].offset;
			return iter;
		}
		cout << "failed\n";
		iter = (iter+1)%MAX_THREADS;
	}
}

ostream& operator << (ostream& os, info_t& info) {
        if(info.file) {
            os << info.file << endl;
            os << tmap[info.tindex] << endl;
        }
        else
            os << "empty" << endl;
        os << info.line << endl;
        os << info.timestamp << endl;
        os << info.size << endl;
        os << info.addr << endl;
        os << info.typeofop << endl;
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

void dumpentirestatstofile() {
    ofstream myfile("info_t_dump.txt", ios_base::out | ios_base::app);
    ofstream filemap("filemap", ios_base::out | ios_base::app);
    ofstream typemap("typemap", ios_base::out | ios_base::app);

    int status;
    char* demangled_name;

    for(int i = 0;i < MAX_TRACK*MAX_THREADS;i++) {
        while(allArrays[i].addr == nullptr) i++;
        
        if(allArrays[i].file && allArrays[i].typeofop && !tmap.count(allArrays[i].tindex)) {
            demangled_name = abi::__cxa_demangle(allArrays[i].tindex.name(), 0, 0, &status);
            tmap[allArrays[i].tindex] = demangled_name;
        }

        if(allArrays[i].file && !fset.count(allArrays[i].file)) {
            fset.insert(allArrays[i].file);
        }
    }

    for(auto i = fset.begin();i != fset.end();i++) {
        filemap.write(*i, sizeof(char*));
        filemap.write(*i, sizeof(*i));
    }

    for(auto i = tmap.begin();i != tmap.end();i++) {
        typemap.write((char*)&(*i).first, sizeof(type_index));
        typemap.write((*i).second, sizeof((*i).second));
    }

    myfile.write(reinterpret_cast<char const*>(allArrays), MAX_THREADS*MAX_TRACK*sizeof(info_t));
}

void dumpentirestatstofile2() {
    it = INT_MAX;
    ofstream myfile("info_t_dump.txt", ios_base::out | ios_base::app);

    int status;
    char* demangled_name;

    for(int i = 0;i < MAX_TRACK*MAX_THREADS;i++) {
        if(allArrays[i].addr == nullptr) continue;
        else if(allArrays[i].file && allArrays[i].typeofop && !tmap.count(allArrays[i].tindex)) {
            demangled_name = abi::__cxa_demangle(allArrays[i].tindex.name(), 0, 0, &status);
            tmap[allArrays[i].tindex] = demangled_name;
        }

        myfile << allArrays[i];
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

void insert_type(void *p, const MemStamp &stamp,const type_index tindex) {
    if(it < MAX_TRACK) {
        myArray[it].file = stamp.filename;
        myArray[it].line = stamp.lineNum;
        myArray[it].tindex = tindex;
        it++;
    }
}

//Helper for malloc
void insert_info(size_t size, void* ptr, type_index tindex) {
    if(!myArray) {
        int result = get_slot(this_thread::get_id());
        myArray = allArrays + MAX_TRACK*result;
    }
    
    if(it < MAX_TRACK) {
        myArray[it].tindex = tindex;
        myArray[it].timestamp = get_server_clock();
        myArray[it].size = size;
        myArray[it].addr = ptr;
        myArray[it].typeofop = true;
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
    
    if(!setup) {
        exiter.add();
        setup = true;
    }

    void* mem = malloc(size == 0?1:size);
    
    if(mem == 0) {
        throw bad_alloc();
    }

    if(!myArray) {
        int result = get_slot(this_thread::get_id());
        myArray = allArrays + MAX_TRACK*result;
    }

    /*ensure that number of allocations don't exceed the limit
    * make a policy for dumping the existing allocations before
    * reaching the limit
    **/

    if(it < MAX_TRACK) {
        myArray[it].timestamp = get_server_clock();
        myArray[it].size = size;
        myArray[it].addr = mem;
        myArray[it].typeofop = true;
    }

    return mem;
}

void *operator new[] (size_t size) {
    if(!setup) {
        exiter.add();
        setup = true;
    }

    void* mem = malloc(size == 0?1:size);
    
    if(mem == 0) {
        throw bad_alloc();
    }

    if(!myArray) {
        int result = get_slot(this_thread::get_id());
        myArray = allArrays + MAX_TRACK*result;
    }

    /*ensure that number of allocations don't exceed the limit
    * make a policy for dumping the existing allocations before
    * reaching the limit
    **/

    if(it < MAX_TRACK) {
        myArray[it].timestamp = get_server_clock();
        myArray[it].size = size;
        myArray[it].addr = mem;
        myArray[it].typeofop = true;
    }

    return mem;
}

void operator delete(void * mem) {
    if(!setup) {
        exiter.add();
        setup = true;
    }

    if(!myArray) {
        int result = get_slot(this_thread::get_id());
        myArray = allArrays + MAX_TRACK*result;
    }
    
    if(it < MAX_TRACK) {
        myArray[it].timestamp = get_server_clock();
        myArray[it].addr = mem;
        myArray[it].typeofop = false;
    }

    free(mem);
}

void operator delete[](void *mem) {
    if(!setup) {
        exiter.add();
        setup = true;
    }
    
    if(!myArray) {
        int result = get_slot(this_thread::get_id());
        myArray = allArrays + MAX_TRACK*result;
    }

    if(it < MAX_TRACK) {
        myArray[it].timestamp = get_server_clock();
        myArray[it].addr = mem;
        myArray[it].typeofop = false;
    }

    free(mem);
}