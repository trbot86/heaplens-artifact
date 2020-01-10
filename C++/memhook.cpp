#include <iostream>
#include <bits/stdc++.h>

template<typename T>
struct track_alloc : std::allocator<T> {
    typedef typename std::allocator<T>::pointer pointer;
    typedef typename std::allocator<T>::size_type size_type;

    //What is this for?
    template<typename U>
    struct rebind {
        typedef track_alloc<U> other;
    };

    track_alloc() {}

    template<typename U>
    track_alloc(track_alloc<U> const& u)
        :std::allocator<T>(u) {}

    pointer allocate(size_type size, 
                     std::allocator<void>::const_pointer = 0) {
        void * p = std::malloc(size * sizeof(T));
        if(p == 0) {
            throw std::bad_alloc();
        }
        return static_cast<pointer>(p);
    }

    void deallocate(pointer p, size_type) {
        std::free(p);
    }
};

typedef std::map< void*, std::size_t, std::less<void*>, 
                  track_alloc< std::pair<void* const, std::size_t> > > track_type;

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
    static track_type * track = new (std::malloc(sizeof *track)) 
        track_type;
    static track_printer printer(track);
    return track;
}

void * operator new(std::size_t size) throw(std::bad_alloc) {
    // we are required to return non-null
    void * mem = std::malloc(size == 0 ? 1 : size);
    if(mem == 0) {
        throw std::bad_alloc();
    }
    (*get_map())[mem] = size;
    return mem;
}

void operator delete(void * mem) throw() {
    if(get_map()->erase(mem) == 0) {
        // this indicates a serious bug
        std::cerr << "bug: memory at " 
                  << mem << " wasn't allocated by us\n";
    }
    std::free(mem);
}

int main() {
    std::string *s = new std::string;
        // will print something like: TRACK: leaked at 0x9564008, 4 bytes
}