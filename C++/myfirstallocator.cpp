#include "myfirstallocator.h"

struct track_printer {
    track_type* track;
    track_printer (track_type* track):track(track) {}
    ~track_printer () {
        track_type::iterator it = track->begin();
        while(it != track->end()) {
            std::cout << "LEAKED: " << it->first 
            << " size: " << it->second.size << " file: " << it->second.file << " func: " << it->second.function << " line: " << it->second.line << "\n";
            ++it;
        }
    }
};

track_type* get_map() {
    static track_type *track = new (std::malloc(sizeof *track)) track_type;
    static track_printer printer(track);
    return track;
}

void dumpstatstofile(const char* file) {
    FILE* fp = fopen(file,"w");
    if(fp == nullptr) {
        throw std::runtime_error(std::strerror(errno));
        return;
    }

    track_type::iterator it = get_map()->begin();
    while(it != get_map()->end()) {
        fprintf(fp,"addr: %p size: %zu line: %d func: %s file: %s time: %lu\n", it->second.addr, it->second.size, it->second.line, it->second.function, it->second.file, it->second.timestamp);
        // fprintf(fp,"addr: %p size: %zu line: %d\n", it->second.addr, it->second.size, it->second.line);
        ++it;
    }

    fclose(fp);
    return;
}

void * operator new(std::size_t size) {
    // we are required to return non-null
    void* mem = std::malloc(size == 0?1:size);
    if(mem == 0) {
        throw std::bad_alloc();
    }

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