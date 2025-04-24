#include "io_handler.hpp"
#include <vector>
#include <cstdlib>

using addr_and_size = std::pair<uintptr_t, size_t>;

class Sampler {
private:
    enum class PageSample { No, Yes, Unknown };
    typedef struct page_info {
        bool has_perf_addr{false};
        PageSample sampled{PageSample::Unknown};
        std::vector<memory_event_t*> event_ptrs{};

        void add_event(memory_event_t& ev) {
            event_ptrs.push_back(&ev);
        }
    } page_info_t;

    IOHandler io;

    std::vector<addr_and_size> split_event(memory_event_t& ev, size_t gran);

    void sample_page(std::unordered_map<uintptr_t, page_info_t>& pages,
                    memory_event_t& ev, size_t page_size, double sample_prop);
public:
    Sampler() : io{} {}

    /*
    call get_all_events (which adds overlap frees)

    iterate over each event (iterator splits events across boundaries?)
        split across boundary?

    uniformly sample the pages
        record all pages that are NOT taken for each type
    at end, if type req not satisifed, sample more pages until it is
    */


    void sample_pages_and_record_stats(size_t page_size, double sample_prop);

    void calc_frag();
};