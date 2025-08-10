#include "hash.h"
#include <errno.h>
#include <stdio.h>


uint16_t memhook_hashtable::insert(const std::type_info* typeid_ptr) {
    uint64_t h = reinterpret_cast<uintptr_t>(typeid_ptr) * 11400714819323198485ull; // Knuth's multiplicative hash function

    for(int i = 0; i < MEMHOOK_HASH_TABLE_SIZE; i++) {
        uint16_t index = (h + i) & (MEMHOOK_HASH_TABLE_SIZE - 1);

        if(!bucket[index].full.load(std::memory_order_acquire)) {
            guard[index].lock();
            if (!bucket[index].full) {
                bucket[index].typeid_ptr = typeid_ptr;
                bucket[index].full.store(true, std::memory_order_release);
                guard[index].unlock();
                return index;
            }
            guard[index].unlock();
        }
        
        if (typeid_ptr == bucket[index].typeid_ptr) {
            // cout << "found" << endl;
            return index;
        }
    }
    return 0;
}
