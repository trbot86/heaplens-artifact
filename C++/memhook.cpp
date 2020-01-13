#include "memhook.h"

typedef std::map<void*, std::size_t, std::less<void*>, track_alloc<std::pair<void* const, std::size_t>>> track_type;

struct track_printer {
    track_type * track;
    track_printer(track_type * track):track(track) {}
    ~track_printer() {
        track_type::const_iterator it = track->begin();
        while(it != track->end()) {
            std::cerr << "TRACK: leaked at " << it->first << ", "
                      << it->second << " bytes\n";
            ++it;
        }
    }
};

track_type * get_map() {
    // don't use normal new to avoid infinite recursion.
    static track_type * track = new (std::malloc(sizeof *track)) track_type;
    static track_printer printer(track);
    return track;
}

// void * operator new(std::size_t size) {
//     void * mem = std::malloc(size == 0 ? 1 : size);
//     if(mem == 0) {
//         throw std::bad_alloc();
//     }
//     (*get_map())[mem] = size;
//     std::cout << mem << "\n";
//     return mem;
// }

void * operator new(std::size_t size, std::string type) {
    // we are required to return non-null
    void * mem = std::malloc(size == 0 ? 1 : size);
    if(mem == 0) {
        throw std::bad_alloc();
    }
    (*get_map())[mem] = size;
    std::cout << mem << " type: " << type << "\n";
    return mem;
}

// void * operator new(std::size_t size) throw(std::bad_alloc) {
//     void * mem = 
// }

// void operator delete(void * mem) throw() {
//     if(get_map()->erase(mem) == 0) {
//         // this indicates a serious bug
//         std::cerr << "bug: memory at " 
//                   << mem << " wasn't allocated by us\n";
//     }
//     else {
//         std::cout << mem << " freed\n";
//     }
//     std::free(mem);
// }

void operator delete(void * mem, std::string type) throw() {
    if(get_map()->erase(mem) == 0) {
        // this indicates a serious bug
        std::cerr << "bug: memory at " 
                  << mem << " wasn't allocated by us\n";
    }
    else {
        std::cout << mem << " freed\n";
    }
    std::free(mem);
}