#include <sqlite3.h>
#include <string>
#include <vector>
#include <unordered_map>
#include "info.hpp"

class IOHandler {
private:
    std::string in_filename,
                out_filename,
                types_filename,
                files_filename;
    
    void add_overlap_frees(std::vector<memory_event_t>&);
public:
    IOHandler() :   in_filename{"binary_dump.txt"},
                    out_filename{"allocs.sqlite"},
                    types_filename{"typeset_dump.txt"},
                    files_filename{"fileset_dump.txt"} {}

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
    */
    std::vector<memory_event_t> get_all_events();

    std::unordered_map<uintptr_t, std::string> get_type_map();

    std::unordered_map<uintptr_t, std::string> get_file_map();

    std::vector<uintptr_t> get_perf_addrs();

    void write_event_to_db(memory_event_t&);
};