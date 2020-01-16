#include "myfirstallocator.h"

struct track_printer {
    track_type* track;
    track_printer (track_type* track):track(track) {}
    ~track_printer () {
        #ifdef DUMPSTATS == 1
        dumpstatstofile("memdump");
        #endif
    }
};

// track_type* get_map() {
//     allArrays = new (std::malloc(sizeof *track * MAX_THREADS)) track_type;
//     static track_printer printer(track);
//     return track;
// }

//Serialise struct in an efficient manner. Bunch of writes will reorder things in file.
void dumpstatstofile(const char* file) {
    int fp = open(file,O_CREAT|O_APPEND|O_RDWR,0666);
    if(fp == -1) {
        throw std::runtime_error(std::strerror(errno));
        return;
    }

    track_type::iterator it = get_map()->begin();
    while(it != get_map()->end()) {
        std::cout << it->second.file << " " << it->second.line << std::endl;
        
        //******* FIGURE OUT DUMPING STRATEGY*************//
        // write(fp, &(it->second.line), sizeof(unsigned int));
        // write(fp, &(it->second.timestamp), sizeof(uint64_t));
        // write(fp, &(it->second.size), sizeof(size_t));
        // write(fp, &(it->second.addr), sizeof(void*));
        ++it;
    }

    close(fp);
    return;
}

void * operator new(std::size_t size) {
    // we are required to return non-null
    static thread_local int it = 0;

    std::experimental::source_location loc = std::experimental::source_location::current();

    info_t info = {
        loc.file_name(),
        loc.function_name(),
        nullptr,
        loc.line(),
        get_server_clock(),
        size,
        mem,
    };
    
    if(myArray) {
        void* mem = std::malloc(size == 0?1:size);
        if(mem == 0) {
            throw std::bad_alloc();
        }
    }

    (*get_map())[mem] = info;
    return mem;
}

void operator delete(void * mem) {    
    if(get_map()->erase(mem) == 0) {
        // this indicates a serious bug
        std::cerr << "bug: memory at " << mem << " wasn't allocated by us\n";
    }
    std::free(mem);
}