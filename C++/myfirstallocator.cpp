#include "myfirstallocator.h"

// void * operator new(std::size_t size) {
//     // we are required to return non-null
//     void * mem = std::malloc(size == 0 ? 1 : size);
//     if(mem == 0) {
//         throw std::bad_alloc();
//     }
//     // std::cout << mem << " type: " << type << "\n";
//     return mem;
// }

// void operator delete(void * mem) {
//     std::free(mem);
// }

template<typename T>
void * operator new(std::size_t size) {
    static track_alloc<T> *talloc;
    // we are required to return non-null
    void* mem = talloc.allocate(size);
    if(mem == 0) {
        throw std::bad_alloc();
    }
    
    std::cout << mem << " type: " << "\n";
    return mem;
}

template<typename T>
void operator delete(void * mem, trackalloc<T>& talloc) throw() {
    talloc.deallocate(mem);
    std::free(mem);
}