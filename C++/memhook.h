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

    pointer allocate(size_type size, std::allocator<void>::const_pointer = 0) {
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

// typedef std::map< void*, std::size_t, std::less<void*>,  track_alloc< std::pair<void* const, std::size_t> > > track_type;