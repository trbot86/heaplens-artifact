#include "hash.h"
#include <errno.h>
#include <stdio.h>


char* memhook_hashtable::insert(const char* str) {
    uint64_t h = djb2(str);

    for(int i = 0; i < MEMHOOK_HASH_TABLE_SIZE; i++) {
        int index = (h + i) & (MEMHOOK_HASH_TABLE_SIZE - 1);

        if (!bucket[index].full) {
            guard[index].lock();
            if (!bucket[index].full) {
                uint16_t len = strlen(str);
                strncpy(bucket[index].str, str, len+1);
                bucket[index].len = len;
                bucket[index].full = true;
                guard[index].unlock();
                return bucket[index].str;
            }
            guard[index].unlock();
        }
        
        if (strcmp(str, bucket[index].str) == 0) {
            // cout << "found" << endl;
            return bucket[index].str;
        }
    }
    return NULL;
}
