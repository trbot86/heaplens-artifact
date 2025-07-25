#include "../io_handler.hpp"
#include "test_data/sampler_test_paths.h"
#include <filesystem>
#include <unordered_set>

#define SUFFIX_LEN 9

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
    std::unordered_set<std::string> names{};

    for (const auto& entry : std::filesystem::directory_iterator(TEST_DATA_DIR)) {
        if (!entry.is_regular_file()) continue;
        std::string filepath = entry.path().filename().string();
        if (filepath.substr(filepath.size() - 4) != ".txt") continue;
        std::string fname = filepath.substr(0, filepath.size() - SUFFIX_LEN);
        if (names.find(fname) != names.end()) continue;

        names.insert(fname);

        IOHandler io{TEST_DATA_DIR + fname + "_dump.txt",
                    TEST_DATA_DIR + fname + "_type.txt",
                    TEST_DATA_DIR + fname + "_file.txt"};
        std::pair<memory_event_t*, size_t> data = io.get_all_events(true);
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
                if (event.typeofop)
                    printf("ERROR: unmapped type in data: %p\n\n", event.tindex_name);
                else
                    printf("WARNING: unfilled type for free at addr %p with ts %lu\n\n",
                            event.addr, event.timestamp);
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
        ans_file.open(TEST_DATA_DIR + fname + ".ans");
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
}