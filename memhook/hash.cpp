#include "hash.h"
#include <errno.h>
#include <stdio.h>

char* memhook_hashtable::insert(string str) {
    uint64_t h = djb2(str);

    // cout << "insert h: " << h << " " << endl;
    memhook_hashtable::hashfunction.setSeed(h);

    for(int i = 0;i < MEMHOOK_HASH_TABLE_SIZE;i++) {
        int index = (hashfunction.next(MEMHOOK_HASH_TABLE_SIZE)+i)%MEMHOOK_HASH_TABLE_SIZE;
        cout << "insert KEY: " << i << " " << index << endl;
        char* found = bucket[index];
        
        if(found == NULL) {
            char* ptr = (char*)malloc(str.size());
            strncpy(ptr, str.c_str(), str.size());
            CASB(&bucket[index], NULL, ptr);
            return ptr;
        }
        else if(strcmp(found, str.c_str()) != 0) {
            return found;
        }
    }
    return NULL;
}

bool memhook_hashtable::contains(string str) {
    uint64_t h = djb2(str);
    // cout << "insert h: " << h << endl;
    memhook_hashtable::hashfunction.setSeed(h);
    
    for(int i = 0;i < MEMHOOK_HASH_TABLE_SIZE;i++) {
        int index = (hashfunction.next(MEMHOOK_HASH_TABLE_SIZE)+i)%MEMHOOK_HASH_TABLE_SIZE;
        cout << "contains KEY: " << i << " " << index << endl;
        char* found = bucket[index];

        if(found == NULL) return false;
        else if(strcmp(found, str.c_str()) != 0) continue;
        else return true;
    }
    return false;
}

unsigned long memhook_hashtable::djb2(const string& str) {
    unsigned long hash = 5381;
    for (size_t i = 0; i < str.size(); ++i)
        hash = 33 * hash + (unsigned char)str[i];
    return hash;
}

// int main(int argc, char** argv) {
//     memhook_hashtable mh;
//     mh.insert("01233");
//     mh.insert("Hello!");

//     cout << mh.contains("Hello!") << endl;
// }