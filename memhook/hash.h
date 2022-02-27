#ifndef __MEMHOOK_HASH_H
#define __MEMHOOK_HASH_H

#include <iostream>
#include <bits/stdc++.h>

#include "memhook_xoshiro256p.h"

#define MEMHOOK_HASH_TABLE_SIZE 1000000

using namespace std;

typedef char* volatile item_t;

class memhook_hashtable {
    public:
    typedef item_t* iterator;
    mhRandom64 hashfunction;
    memhook_hashtable() {};
    char* insert(const char* str);
    bool contains(const char* str);
    item_t bucket[MEMHOOK_HASH_TABLE_SIZE] = { NULL };
    unsigned long djb2(const char* str);
};


#endif //__MEMHOOK_HASH_H