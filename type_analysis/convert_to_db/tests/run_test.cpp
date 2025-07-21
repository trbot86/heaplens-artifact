#include "../io_handler.hpp"
#include "test_data/sampler_test_paths.h"

typedef struct type_tracker {
    std::string type_name;
    size_t num_allocs;
    size_t size_allocs;
    size_t num_frees;
    size_t size_frees;
} type_tracker_t;

void check_stats(std::string type, std::string event_kind, size_t num_observed,
                size_t size_observed, size_t num_expect, size_t size_expect) {
    if (num_observed != num_expect || size_observed != size_expect) {
        printf("ERROR: stats for type %s %s does not match expected\n"
                "\tObserved: num=%lu, size=%lu\n"
                "\tExpected: num=%lu, size=%lu\n\n", type.c_str(), event_kind.c_str(),
                                                    num_observed, size_observed,
                                                    num_expect, size_expect);
    }
    else {
        printf("%s stats for type %s ok!\n", event_kind.c_str(), type.c_str());
    }
}

int main() {
    IOHandler io{TEST_DATA_DIR "generate_small_static_dump.txt",
                TEST_DATA_DIR "generate_small_static_type.txt",
                TEST_DATA_DIR "generate_small_static_file.txt"};
    std::pair<memory_event_t*, size_t> data = io.get_all_events();
    std::unordered_map<uintptr_t, std::string> type_map = io.get_type_map();
    auto stats = std::unordered_map<std::string, type_tracker_t>{};
    for (auto t : type_map) {
        stats[t.second] = type_tracker_t{t.second, 0, 0, 0, 0};
    }
    for (int i = 0; i < data.second; i++) {
        memory_event_t event = data.first[i];
        std::string tname;
        uintptr_t tindex_ptr = reinterpret_cast<uintptr_t>(event.tindex_name);
        if (type_map.find(tindex_ptr) == type_map.end()) {
            printf("ERROR: unmapped type in data: %p\n\n", event.tindex_name);
            continue;
        }
        else
            tname = type_map[tindex_ptr];
        
        if (event.typeofop) {
            stats[tname].num_allocs++;
            stats[tname].size_allocs += event.size;
        }
        else {
            stats[tname].num_frees++;
            stats[tname].size_frees += event.size;
        }
    }

    std::ifstream ans_file;
    ans_file.open("test_data/generate_small_static.ans");
    std::string type, event_kind;
    size_t num, total_size;
    while (ans_file >> type >> num >> total_size >> event_kind) {
        if (stats.find(type) == stats.end()) {
            printf("ERROR: type %s not observed\n\n", type.c_str());
        }
        else {
            size_t num_observed = (event_kind == "alloc" ? stats[type].num_allocs : stats[type].num_frees);
            size_t size_observed = (event_kind == "alloc" ? stats[type].size_allocs : stats[type].size_frees);
            check_stats(type, event_kind, num_observed, size_observed, num, total_size);
        }
    }
    ans_file.close();
}