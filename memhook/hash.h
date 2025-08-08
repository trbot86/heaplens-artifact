#ifndef __MEMHOOK_HASH_H
#define __MEMHOOK_HASH_H

#include <iostream>
#include <bits/stdc++.h>
#include <mutex>

// #include "memhook_xoshiro256p.h"

#define MEMHOOK_HASH_TABLE_SIZE 1024    // must be a power of 2
#define MEMHOOK_MAX_ENTRY_SIZE 320

using namespace std;

typedef char* memhook_hash_item_t;

struct alignas(64) entry {
    char str[MEMHOOK_MAX_ENTRY_SIZE - sizeof(uint16_t) - sizeof(std::atomic<bool>)];
    uint16_t len;
    std::atomic<bool> full;

    entry() : full(false) {}
};

class memhook_hashtable {
public:
    template<int ind>
    bool strcmp_memhook(char* ptr) {
        return *ptr == '\0';
    }

    template<int ind, char first, char... rest>
    bool strcmp_memhook(char* ptr) {
        return *ptr == first && strcmp_memhook<0, rest...>(ptr + 1);
    }

    template<int ind>
    void insert_helper(char* ptr) {
        *ptr = '\0';
    }

    template<int ind, char first, char... rest>
    void insert_helper(char* ptr) {
        *ptr = first;
        insert_helper<0, rest...>(ptr + 1);
    }

    template<char... str>
    char* insert() {
        uint64_t h = djb2<5381, str...>();

        for (int i = 0; i < MEMHOOK_HASH_TABLE_SIZE; i++) {
            int index = (h + i) & (MEMHOOK_HASH_TABLE_SIZE - 1);

            if(!bucket[index].full.load(std::memory_order_acquire)) {
                guard[index].lock();
                if (!bucket[index].full) {
                    insert_helper<0, str...>(bucket[index].str);
                    bucket[index].len = strlen(bucket[index].str);
                    bucket[index].full.store(true, std::memory_order_release);
                    guard[index].unlock();
                    return bucket[index].str;
                }
                guard[index].unlock();
            }
            
            if (strcmp_memhook<0, str...>(bucket[index].str)) {
                // cout << "found" << endl;
                return bucket[index].str;
            }
        }
        return NULL;
    }

    char* insert(const char* str);
    
    entry bucket[MEMHOOK_HASH_TABLE_SIZE];
    mutex guard[MEMHOOK_HASH_TABLE_SIZE];

    template<uint64_t hash>
    uint64_t djb2() {
        return hash;
    }

    template<uint64_t hash, char first, char... str>
    uint64_t djb2() {
        if (first == '\0')
            return hash;
        return djb2<33 * hash + (unsigned char) first, str...>();
    }

    inline uint64_t djb2(const char* str) {
        unsigned long hashval = 5381;
        while (*str) {
            hashval = 33 * hashval + (unsigned char)(*str);
            str++;
        }
        return hashval;
    }
};

#endif //__MEMHOOK_HASH_H