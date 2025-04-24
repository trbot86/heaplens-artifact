#include <cstdint>
#include <stddef.h>

#pragma once

typedef struct memory_event {
    const char* file;
    const char* tindex_name;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;
} memory_event_t;