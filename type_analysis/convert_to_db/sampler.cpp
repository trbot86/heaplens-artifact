#include "sampler.hpp"

std::vector<addr_and_size> Sampler::split_event(memory_event_t& ev, size_t gran) {
    std::vector<addr_and_size> ret{};
    uintptr_t curr_chunk_addr = reinterpret_cast<uintptr_t>(ev.addr);
    size_t curr_chunk_size;
    int64_t rem_size = ev.size;
    while (rem_size > 0) {
        curr_chunk_size = 
            std::min(gran - (curr_chunk_addr % gran), ev.size);
        ret.push_back(addr_and_size{curr_chunk_addr, curr_chunk_size});
        curr_chunk_addr += curr_chunk_size;
        rem_size -= curr_chunk_size;
    }
    return ret;
}

void Sampler::sample_page(std::unordered_map<uintptr_t, page_info_t>& pages,
                        memory_event_t& ev, uintptr_t page_addr, double sample_prop) {
    if (pages.find(page_addr) == pages.end())
        pages.insert(std::pair<uintptr_t, page_info_t>{page_addr, page_info_t{}});
    
    pages[page_addr].add_event(ev);
    if (pages[page_addr].sampled == PageSample::Unknown) {
        pages[page_addr].sampled = (rand() < sample_prop*RAND_MAX) ?
                                    PageSample::Yes : PageSample::No;
    }
}

void Sampler::sample_pages_and_record_stats(size_t page_size, double sample_prop) {
    auto ts_to_event = io.get_all_events();
    std::unordered_map<uintptr_t, page_info_t> pages{};

    for (auto& event : ts_to_event) {
        for (auto& addr_sz : split_event(event, page_size)) {
            memory_event_t sp_ev{event.file, event.tindex_name, event.line,
                                event.timestamp, addr_sz.second,
                                reinterpret_cast<void*>(addr_sz.first),
                                event.typeofop};
            uintptr_t page_addr = reinterpret_cast<uintptr_t>(sp_ev.addr) / page_size;
            sample_page(pages, sp_ev, page_addr, sample_prop);

            if (pages[page_addr].sampled == PageSample::Yes) {
                io
            }
        }
    }
}