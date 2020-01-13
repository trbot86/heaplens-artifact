#include <iostream>
#include <bits/stdc++.h>

void* operator new (std::size_t);
void operator delete (void* ptr);

template<typename T>
struct internalalloc: std::allocator<T> {
    typedef typename std::allocator<T>::pointer pointer;
    typedef typename std::allocator<T>::size_type size_type;

    template<typename U>
    struct rebind {
        typedef internalalloc<U> other;
    };

    internalalloc() {}

    template<typename U>
    internalalloc(internalalloc<U> const& u): std::allocator<T>(u) {}

    pointer allocate(size_type size, std::allocator<void>::const_pointer = 0) {
        void* ptr = malloc(size*sizeof(T));
        std::cout << "allocating\n";
        if(ptr == 0) {
            throw std::bad_alloc();
        }
        return static_cast<pointer>(ptr);
    }

    void deallocate(pointer p, size_type) {
        std::free(p);
    }
};

typedef std::map<void*, std::size_t, std::less<void*>, internalalloc<std::pair<void* const, std::size_t>> > track_type;

template<typename T>
struct trackalloc: std::allocator<T> {
    typedef typename std::allocator<T>::pointer pointer;
    typedef typename std::allocator<T>::size_type size_type;

    template<typename U>
    struct rebind {
        typedef trackalloc<U> other;
    };

    trackalloc() {}

    template<typename U>
    trackalloc(trackalloc<U> const& u): std::allocator<T>(u) {}

    pointer allocate(size_type size, std::allocator<void>::const_pointer = 0) {
        void* ptr = malloc(size*sizeof(T));
        if(ptr == 0) {
            throw std::bad_alloc();
        }
        std::cout << "tallocating\n";
        (*get_map())[ptr] = size*sizeof(T);
        return static_cast<pointer>(ptr);
    }

    void deallocate(pointer p, size_type) {
        if(get_map()->erase(p) == 0) {
            std::cout << "another external allocator in use!\n";
        }
        std::free(p);
    }

    struct track_printer {
        track_type* track;
        track_printer (track_type* track):track(track) {}
        ~track_printer () {
            track_type::iterator it = track->begin();
            while(it != track->end()) {
                std::cout << "LEAKED: " << it->first << " size: " << it->second << "\n";
                ++it;
            }
        }
    };

    track_type* get_map() {
        static track_type *track = new (std::malloc(sizeof *track)) track_type;
        static track_printer printer(track);
        return track;
    }
};