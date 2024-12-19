#ifndef __MEMHOOK_HASH_H
#define __MEMHOOK_HASH_H

#include <iostream>
#include <bits/stdc++.h>
#include <mutex>

#include "memhook_xoshiro256p.h"

#define MEMHOOK_HASH_TABLE_SIZE 10000
#define MEMHOOK_MAX_STRING_SIZE 1000
#define MEMHOOK_HASH_VAL 5381;

using namespace std;

typedef char* volatile memhook_hash_item_t;

struct entry {
    char str[MEMHOOK_MAX_STRING_SIZE];
    volatile bool full;

    entry() : full(false) {}
};

class memhook_hashtable {
public:
    typedef memhook_hash_item_t* iterator;
    mhRandom64 hashfunction;
    memhook_hashtable() {};

    template<int ind>
    bool strcmp_memhook(char* ptr) {
        return *ptr == '\0';
    }

    template<int ind, char first, char... rest>
    bool strcmp_memhook(char* ptr) {
        if (*ptr == first)
            return strcmp_memhook<0, rest...>(ptr + 1);
        return false;
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

        for(int i = 0;i < MEMHOOK_HASH_TABLE_SIZE;i++) {
            int index = (h + i) % MEMHOOK_HASH_TABLE_SIZE;

            if(!bucket[index].full) {
                guard[index].lock();
                if (!bucket[index].full) {
                    insert_helper<0, str...>(bucket[index].str);
                    bucket[index].full = true;
                    guard[index].unlock();
                    return bucket[index].str;
                }
                guard[index].unlock();

                if (strcmp_memhook<0, str...>(bucket[index].str)) {
                    return bucket[index].str;
                }
                else {
                    continue;
                }
            }
            else if(strcmp_memhook<0, str...>(bucket[index].str)) {
                // cout << "found" << endl;
                return bucket[index].str;
            }
        }
        return NULL;
    }

    char* insert(const char* str);
    
    entry bucket[MEMHOOK_HASH_TABLE_SIZE];
    mutex guard[MEMHOOK_HASH_TABLE_SIZE];

    template<unsigned long hash>
    unsigned long djb2() {
        return hash;
    }

    template<unsigned long hash, char first, char... str>
    unsigned long djb2() {
        if (first == '\0')
            return hash;
        return djb2<33 * hash + (unsigned char) first, str...>();
    }

    template<unsigned long hash>
    unsigned long djb2(const char* str) {
        unsigned long hashval = hash;
        for (size_t i = 0; i < strlen(str); ++i)
            hashval = 33 * hashval + (unsigned char)str[i];
        return hashval;
    }
};

#endif //__MEMHOOK_HASH_H