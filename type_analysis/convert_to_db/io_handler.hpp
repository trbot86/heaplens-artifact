#include <sqlite3.h>
#include <map>
#include <unordered_map>
#include <algorithm>
#include <vector>
#include <set>
#include <iostream>
#include <fstream>
#include <sys/stat.h>
#include <sys/mman.h>
#include <regex>
#include "memory_event.hpp"

class IOHandler {
private:
    typedef struct field_data {
        std::string subtype;
        size_t size;
        size_t offset;
    } field_data_t;

    sqlite3* db;
    char* zErrMsg;
    std::string in_filename,
                out_filename,
                types_filename,
                files_filename,
                frag_filename;
    std::unordered_map<uintptr_t, std::string> file_map, type_map;
    std::unordered_map<std::string, uintptr_t> rev_file_map;
    std::unordered_map<memory_event_t, mem_interval_t> event_interval_info;

    void free_all_descendants(std::vector<memory_event_t>&,
                        std::set<mem_interval_t*, std::function<bool (mem_interval_t*, mem_interval_t*)>>&,
                        uint64_t,
                        mem_interval_t*,
                        bool add_event=true);
    
    void sort_and_add_overlap_frees(std::vector<memory_event_t>&);

    std::unordered_map<uintptr_t, std::string> construct_map(std::string, bool remove_volatile=false);

    void step_and_clear_bindings(sqlite3_stmt*);

public:
    IOHandler();

    ~IOHandler();

    /*
    Returns a list of all memory events in in_filename in nondecreasing
    order of their timestamps. Also adds frees to overlapping allocations
    as follows:
        - If one allocation is completely contained within a previous allocation,
        then the latter is treated as a container and is not immediately freed.
        When a container is freed, all of its descendants are freed as well.
        - If an allocation has the same address & size as a previous allocation
        or it partially overlaps a previous allocation, then the previous
        allocation is freed.
    
    Adds size and type info to free events

    Fills in the event_interval_info map to help calculate fragmentation
    */
    std::vector<memory_event_t> get_all_events();

    std::unordered_map<memory_event_t, mem_interval_t> get_event_interval_info();

    std::unordered_map<uintptr_t, std::unordered_map<uintptr_t, perf_data_t>> get_perf_addrs(
        std::string perf_filename, size_t page_size, size_t cl_size, double cutoff);

    std::unordered_set<file_and_line_num_t> include_frag_allocs();

    void begin_transaction();

    void end_transaction();

    void prepare_write_to_supertable(sqlite3_stmt**);

    void prepare_write_to_fields(sqlite3_stmt**);

    void prepare_write_to_perf(sqlite3_stmt**);

    void prepare_write_to_lines(sqlite3_stmt**);

    void prepare_write_to_stats(sqlite3_stmt**);

    void prepare_write_to_align(sqlite3_stmt**);

    void write_event_to_db(sqlite3_stmt*, memory_event_t&, uintptr_t actual_addr=0);

    void write_lines_to_db(std::unordered_map<uintptr_t, std::vector<int64_t>>&);

    void write_perf_to_db(sqlite3_stmt*, uintptr_t, double, size_t, size_t);

    void write_fields_to_db(std::string);

    void write_stat_to_db(sqlite3_stmt*, uintptr_t, size_t, size_t);

    void write_align_to_db(sqlite3_stmt*, uintptr_t, size_t, size_t, uint64_t);
};