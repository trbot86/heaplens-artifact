#include <cstdint>
#include <stddef.h>
#include <unordered_set>
#include <cstring>
#include <functional>
#include <string>
#include <cassert>

#pragma once

using file_and_line_num_t = std::pair<uintptr_t, unsigned int>;
using addr_and_size = std::pair<uintptr_t, size_t>;

typedef struct memory_event {
    const char* file;
    const char* tindex_name;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;

    bool operator==(const struct memory_event& other) const {
        return  file == other.file &&
                tindex_name == other.tindex_name &&
                line == other.line &&
                timestamp == other.timestamp &&
                size == other.size &&
                addr == other.addr &&
                typeofop == other.typeofop;
    }
} memory_event_t;

template<>
struct std::hash<memory_event_t> {
    std::size_t operator()(const memory_event_t& ev) const noexcept {
        std::size_t h1 = std::hash<uint64_t>{}(static_cast<uint64_t>(ev.timestamp));
        std::size_t h2 = std::hash<void*>{}(ev.addr);
        std::size_t h3 = std::hash<std::size_t>{}(ev.size);
        return h1 ^ (h2 << 1) ^ (h3 << 1);
    }
};

template<>
struct std::hash<std::pair<uintptr_t, unsigned int>> {
    std::size_t operator()(const std::pair<uintptr_t, unsigned int>& p) const noexcept {
        std::size_t h1 = std::hash<uintptr_t>{}(p.first);
        std::size_t h2 = std::hash<unsigned int>{}(p.second);
        return h1 ^ (h2 << 1);
    }
};

typedef struct size_and_event_list {
    size_t size;
    std::vector<addr_and_size> events;
} size_and_event_list_t;

enum class Overlap { None, Overwritten, Contains };

typedef struct mem_interval {
    uintptr_t start, end;
    struct mem_interval* container;
    std::unordered_set<struct mem_interval*> contained;
    memory_event_t* alloc_info;

    /*
    Here, 'other' represents an allocation that was performed AFTER 'this'
    allocation. The following function returns
        Overlap::Contains iff the interval of 'other' is completely
            contained within the interval of 'this'. This represents the
            scenario in which 'this' was allocated as a container and
            'other' was initialized within 'this' using placement new.
        Overlap::Overwritten iff the interval of 'other' overlaps the
            interval of 'this', but is either (1) exactly equal to the
            interval of 'this', or (2) only partially overlaps the interval
            of 'this'.
        Overlap::None iff the intervals of 'other' and 'this' do not overlap
            at all.
    */
    Overlap contains(struct mem_interval* other) {
        uintptr_t my_start = reinterpret_cast<uintptr_t>(alloc_info->addr);
        uintptr_t other_start = 
            reinterpret_cast<uintptr_t>(other->alloc_info->addr);
        uintptr_t my_end = my_start +
            reinterpret_cast<uintptr_t>(alloc_info->size);
        uintptr_t other_end = other_start +
            reinterpret_cast<uintptr_t>(other->alloc_info->size);
        
        return (my_start <= other_start && my_end > other_end ||
                my_start < other_start && my_end >= other_end) ?
                Overlap::Contains :
                (my_start >= other_end || my_end <= other_start) ?
                Overlap::None : Overlap::Overwritten;
    }
} mem_interval_t;