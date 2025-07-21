#include "hash.h"
#include <errno.h>
#include <stdio.h>

extern void * (*next_malloc)(size_t size);

// template<int ind>
// bool strcmp_memhook(char* ptr) {
//     return *ptr == '\0';
// }

// template<int ind, char first, char... rest>
// bool strcmp_memhook(char* ptr) {
//     if (*ptr == first)
//         return strcmp_memhook<rest...>(ptr + 1);
//     return false;
// }

// template<int ind>
// void insert_helper(char* ptr) {
//     *ptr = '\0';
// }

// template<int ind, char first, char... rest>
// void insert_helper(char* ptr) {
//     *ptr = first;
//     insert_helper<rest...>(ptr + 1);
// }

// template<char... str>
// char* memhook_hashtable::insert() {
//     uint64_t h = djb2<5381>(str...);

//     for(int i = 0;i < MEMHOOK_HASH_TABLE_SIZE;i++) {
//         int index = (h + i) % MEMHOOK_HASH_TABLE_SIZE;
//         struct entry found = bucket[index];

//         if(!found.full) {
//             guard[index].lock();
//             if (!found.full) {
//                 insert_helper<0, str...>(found.str);
//                 found.full = true;
//                 guard[index].unlock();
//                 return found.str;
//             }
//             guard[index].unlock();

//             if (strcmp_memhook<0, str...>(found.str)) {
//                 return found.str;
//             }
//             else {
//                 continue;
//             }
//         }
//         else if(strcmp_memhook<0, str...>(found.str)) {
//             // cout << "found" << endl;
//             return found.str;
//         }
//     }
//     return NULL;
// }

char* memhook_hashtable::insert(const char* str) {
    uint64_t h = djb2<5381>(str);
    // cout << "TESTING" << endl;

    for(int i = 0;i < MEMHOOK_HASH_TABLE_SIZE;i++) {
        int index = (h + i) % MEMHOOK_HASH_TABLE_SIZE;

        if(!bucket[index].full) {
            guard[index].lock();
            if (!bucket[index].full) {
                strncpy(bucket[index].str, str, strlen(str)+1);
                bucket[index].full = true;
                guard[index].unlock();
                return bucket[index].str;
            }
            guard[index].unlock();

            if (strcmp(str, bucket[index].str) == 0) {
                return bucket[index].str;
            }
            else {
                continue;
            }
        }
        else if(strcmp(str, bucket[index].str) == 0) {
            // cout << "found" << endl;
            return bucket[index].str;
        }
    }
    return NULL;
}

// bool memhook_hashtable::contains(const char* str) {
//     uint64_t h = djb2(str);
//     // cout << "insert h: " << h << endl;
//     // memhook_hashtable::hashfunction.setSeed(h);
    
//     for(int i = 0;i < MEMHOOK_HASH_TABLE_SIZE;i++) {
//         int index = (h+i)%MEMHOOK_HASH_TABLE_SIZE;
//         // cout << "contains KEY: " << i << " " << index << endl;
//         char* found = bucket[index];

//         if(found == NULL) return false;
//         else if(strcmp(found, str) != 0) continue;
//         else return true;
//     }
//     return false;
// }

// template<unsigned long hash>
// unsigned long memhook_hashtable::djb2() {
//     return hash;
// }

// template<unsigned long hash, char first, char... str>
// unsigned long memhook_hashtable::djb2() {
//     return djb2<33 * hash + (unsigned char) first, str...>();
// }

// template<unsigned long hash>
// unsigned long memhook_hashtable::djb2(const char* str) {
//     unsigned long hashval = hash;
//     for (size_t i = 0; i < strlen(str); ++i)
//         hashval = 33 * hashval + (unsigned char)str[i];
//     return hashval;
// }

// int main(int argc, char** argv) {
//     memhook_hashtable mh;
//     mh.insert("01233");
//     mh.insert("Hello!");
//     mh.insert("Hello!");

//     cout << mh.contains("Hello!") << endl;
// }