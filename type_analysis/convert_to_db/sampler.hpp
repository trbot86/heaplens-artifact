#include "io_handler.hpp"
#include <vector>
#include <cstdlib>
#include <cmath>

using event_and_actual_addr = std::pair<memory_event_t*, uintptr_t>;

class Sampler {
private:
    enum class PageSample { No, Yes, Unknown };

    typedef struct tp_stats {
        uint64_t num_allocs;
        std::unordered_map<size_t, std::unordered_map<size_t, uint64_t>> align_to_size_to_count;
        std::unordered_set<uintptr_t> resident_pages;
    } tp_stats_t;

    typedef struct page_info {
        bool has_perf_addr{false};
        PageSample sampled{PageSample::Unknown};
        std::vector<event_and_actual_addr*> event_ptrs{};

        void add_event(event_and_actual_addr* ev) {
            event_ptrs.push_back(ev);
        }
    } page_info_t;

    IOHandler io;
    std::vector<memory_event_t> all_events;
    std::unordered_map<uintptr_t, std::unordered_map<uintptr_t, perf_data_t>> perf_pages;
    std::unordered_set<uintptr_t> seen_perf_pages;

    std::vector<addr_and_size> split_event(memory_event_t& ev, size_t gran);

    void sample_page_and_add_event(std::unordered_map<uintptr_t, page_info_t>& pages,
                    event_and_actual_addr* new_event, uintptr_t page_addr, 
                    double sample_prop);

    uint64_t get_bucket(uint64_t, size_t, uint64_t, uint64_t);

    void record_perf_addrs();

    void record_stats_and_align(std::unordered_map<uintptr_t, tp_stats_t>);
    
public:
    Sampler();

    ~Sampler();

    /*
    Save all of the addresses from the provided perf file with hitm >= cutoff.
    Calling sample_pages_and_record_stats later will keep all pages containing
    a perf address.
    */
    void note_perf_addrs(std::string, size_t, size_t, double);

    void record_fields(std::string field_filename);

    void sample_pages_and_record_stats(size_t, size_t, size_t, size_t, double);

    void output_frag(size_t frag_gran);
};