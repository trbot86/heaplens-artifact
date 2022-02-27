#include "hash.h"
#include <errno.h>
#include <stdio.h>

extern void * (*next_malloc)(size_t size);

char* memhook_hashtable::insert(const char* str) {
    uint64_t h = djb2(str);

    // cout << "STRING: " << str << " " << endl;
    // memhook_hashtable::hashfunction.setSeed(h);

    for(int i = 0;i < MEMHOOK_HASH_TABLE_SIZE;i++) {
        int index = (h+i)%MEMHOOK_HASH_TABLE_SIZE;
        // cout << "insert KEY: " << i << " " << index << endl;
        char* found = bucket[index];
        
        if(found == NULL) {
            char* ptr = (char*)next_malloc(strlen(str)+1);
            strncpy(ptr, str, strlen(str)+1);
            // cout << "STRING: " << ptr << endl;
            if(CASB(&bucket[index], NULL, ptr)) {
                return ptr;
            }
            else if (strcmp(bucket[index], str) == 0) {
                return bucket[index];
            }
            else {
                continue;
            }
        }
        else if(strcmp(found, str) == 0) {
            // cout << "found" << endl;
            return found;
        }
    }
    return NULL;
}

bool memhook_hashtable::contains(const char* str) {
    uint64_t h = djb2(str);
    // cout << "insert h: " << h << endl;
    // memhook_hashtable::hashfunction.setSeed(h);
    
    for(int i = 0;i < MEMHOOK_HASH_TABLE_SIZE;i++) {
        int index = (h+i)%MEMHOOK_HASH_TABLE_SIZE;
        // cout << "contains KEY: " << i << " " << index << endl;
        char* found = bucket[index];

        if(found == NULL) return false;
        else if(strcmp(found, str) != 0) continue;
        else return true;
    }
    return false;
}

unsigned long memhook_hashtable::djb2(const char* str) {
    unsigned long hash = 5381;
    for (size_t i = 0; i < strlen(str); ++i)
        hash = 33 * hash + (unsigned char)str[i];
    return hash;
}

// int main(int argc, char** argv) {
//     memhook_hashtable mh;
//     mh.insert("01233");
//     mh.insert("Hello!");
//     mh.insert("Hello!");

//     cout << mh.contains("Hello!") << endl;
// }