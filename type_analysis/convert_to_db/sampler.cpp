#include "sampler.hpp"

Sampler::Sampler() : io{},
            perf_pages{std::unordered_map<uintptr_t, std::unordered_map<uintptr_t, perf_data_t>>{}},
            seen_perf_pages{std::unordered_set<uintptr_t>{}} {
            
    auto events_and_size = io.get_all_events();
    all_events = events_and_size.first;
    num_events = events_and_size.second;
}

Sampler::~Sampler() {}

std::vector<addr_and_size> Sampler::split_event(memory_event_t& ev, size_t gran) {
    std::vector<addr_and_size> ret{};
    uintptr_t curr_chunk_addr = reinterpret_cast<uintptr_t>(ev.addr);
    size_t curr_chunk_size = std::min(gran - (curr_chunk_addr % gran), ev.size);
    int64_t rem_size = ev.size;
    while (rem_size > 0) {
        ret.push_back(addr_and_size{curr_chunk_addr, curr_chunk_size});
        curr_chunk_addr += curr_chunk_size;
        rem_size -= curr_chunk_size;
        curr_chunk_size = std::min(rem_size, static_cast<int64_t>(gran));
    }
    return ret;
}

void Sampler::sample_page_and_add_event(std::unordered_map<uintptr_t, page_info_t>& pages,
                        event_and_actual_addr* new_event, uintptr_t page_num, 
                        double sample_prop) {
    if (pages.find(page_num) == pages.end())
        pages.insert(std::pair<uintptr_t, page_info_t>{page_num, page_info_t{}});
    
    pages[page_num].add_event(new_event);
    if (pages[page_num].sampled == PageSample::Unknown) {
        if (perf_pages.find(page_num) != perf_pages.end()) {
            seen_perf_pages.insert(page_num);
            pages[page_num].sampled = PageSample::Yes;
        }
        else if (sample_prop >= 1.0 || rand() < sample_prop*(RAND_MAX + 1.0)) {
            pages[page_num].sampled = PageSample::Yes;
        }
        else {
            pages[page_num].sampled = PageSample::No;
        }
    }

    assert(pages[page_num].sampled == PageSample::Yes 
            || pages[page_num].sampled == PageSample::No);
}

size_t Sampler::get_bucket(uint64_t ts, size_t num_buckets, uint64_t min_ts,
                            uint64_t max_ts) {
    uint64_t size_of_bucket = std::max((max_ts - min_ts) / num_buckets, (uint64_t) 1);
    return std::ceil(((double) ts - (double) min_ts) / (double) size_of_bucket);
}

void Sampler::note_perf_addrs(std::string perf_filename, size_t page_size, 
                                size_t cl_size, double cutoff) {
    perf_pages = io.get_perf_addrs(perf_filename, page_size, cl_size, cutoff);
}

void Sampler::record_fields(std::string field_filename) {
    io.write_fields_to_db(field_filename);
}

void Sampler::record_perf_addrs() {
    io.begin_transaction();
    sqlite3_stmt* stmt;
    io.prepare_write_to_perf(&stmt);
    for (auto& page_addr : seen_perf_pages) {
        for (auto& entry : perf_pages[page_addr]) {
            io.write_perf_to_db(stmt, entry.first, entry.second.hitm,
                                entry.second.loads, entry.second.stores);
        }
    }
    io.end_transaction();
}

void Sampler::record_stats_and_align(std::unordered_map<uint16_t, tp_stats_t> tp_stats) {
    io.begin_transaction();
    sqlite3_stmt* stmt_stats;
    sqlite3_stmt* stmt_align;
    io.prepare_write_to_stats(&stmt_stats);
    io.prepare_write_to_align(&stmt_align);
    for (auto& entry : tp_stats) {
        uintptr_t tp = entry.first;
        tp_stats_t stat = entry.second;
        io.write_stat_to_db(stmt_stats, tp, stat.num_allocs, stat.resident_pages.size());
        for (auto& align_c : stat.align_to_size_to_count) {
            for (auto& size_c : align_c.second) {
                io.write_align_to_db(stmt_align, tp, align_c.first, size_c.first, size_c.second);
            }
        }
    }
    io.end_transaction();
}

void Sampler::sample_pages_and_record_stats(size_t page_size, size_t num_pages_per_tp,
                                            size_t cache_line_size, size_t num_buckets,
                                            double sample_prop) {
    std::unordered_map<uintptr_t, page_info_t> pages{};
    std::unordered_map<uint16_t, std::vector<int64_t>> buckets{};
    uint64_t min_ts = all_events[0].timestamp;
    uint64_t max_ts = all_events[num_events - 1].timestamp;
    std::unordered_map<uint16_t, tp_stats_t> tp_stats{};

    io.begin_transaction();
    sqlite3_stmt* stmt;
    io.prepare_write_to_supertable(&stmt);
    for (size_t i = 0; i < num_events; i++) {
        auto event = all_events[i];
        uintptr_t event_addr = reinterpret_cast<uintptr_t>(event.addr);
        if (buckets.find(event.tindex_name) == buckets.end()) {
            buckets.insert(std::pair<uintptr_t, std::vector<int64_t>>{
                event.tindex_name,
                std::vector<int64_t>(num_buckets+2, 0)
            });
        }
        size_t event_bucket = get_bucket(event.timestamp, num_buckets, min_ts, max_ts);
        if (event.typeofop) {
            buckets[event.tindex_name][event_bucket] += event.size;
            if (tp_stats.find(event.tindex_name) == tp_stats.end()) {
                tp_stats.insert({event.tindex_name, 
                    tp_stats_t{
                        0,
                        std::unordered_map<size_t, std::unordered_map<size_t, uint64_t>>{},
                        std::unordered_set<uintptr_t>{}
                    }});
            }
            size_t event_align = event_addr % cache_line_size;
            tp_stats[event.tindex_name].num_allocs++;
            tp_stats[event.tindex_name].align_to_size_to_count[event_align][event.size]++;
        }
        else {
            buckets[event.tindex_name][event_bucket] -= event.size;
        }

        for (auto& addr_sz : split_event(event, page_size)) {
            memory_event_t* sp_ev = new memory_event_t{
                                                    event.line,
                                                    event.timestamp,
                                                    addr_sz.second,
                                                    reinterpret_cast<void*>(addr_sz.first),
                                                    event.file,
                                                    event.tindex_name,
                                                    event.typeofop
                                                };
            uintptr_t page_num = reinterpret_cast<uintptr_t>(sp_ev->addr) / page_size;

            if (event.typeofop) {
                tp_stats[event.tindex_name].resident_pages
                    .insert(addr_sz.first / page_size);
            }

            event_and_actual_addr* new_event = new event_and_actual_addr{sp_ev, event_addr};
            sample_page_and_add_event(pages, new_event, page_num, sample_prop);
            if (pages[page_num].sampled == PageSample::Yes) {
                io.write_event_to_db(stmt, *sp_ev, event_addr);
            }
        }
    }

    /*
    After the initial sampling stage, it is possible that some types are still underrepresented
    (i.e. we have taken fewer than num_pages_per_tp pages containing at least one allocation
    of some type T). The following loop takes care of this possibility.
    */
    for (const auto& tp_and_stats : tp_stats) {
        // Statistics already hold distinct pages containing allocations of T.
        // Count pages, not events, including pages selected for earlier types.
        const auto& resident_pages = tp_and_stats.second.resident_pages;
        size_t num_taken = 0;
        for (auto page_num : resident_pages) {
            if (pages.at(page_num).sampled == PageSample::Yes)
                ++num_taken;
        }
        for (auto page_num : resident_pages) {
            if (num_taken >= num_pages_per_tp)
                break;
            auto& page = pages.at(page_num);
            if (page.sampled == PageSample::Yes)
                continue;
            page.sampled = PageSample::Yes;
            for (auto* mem_event : page.event_ptrs) {
                io.write_event_to_db(stmt, *mem_event->first, mem_event->second);
            }
            ++num_taken;
        }
    }
    io.end_transaction();

    for (auto& bucket : buckets) {
        for (int i = 1; i < bucket.second.size(); i++) {
            bucket.second[i] += bucket.second[i-1];
        }
    }
    io.write_lines_to_db(buckets);

    if (seen_perf_pages.size() > 0)
        record_perf_addrs();

    record_stats_and_align(tp_stats);
}

void Sampler::output_frag(size_t frag_gran) {
    auto include_allocs = io.include_frag_allocs();
    auto event_interval_info = io.get_event_interval_info();
    std::unordered_map<uintptr_t, std::map<uintptr_t, size_t>> chunk_map{};
    std::unordered_map<uintptr_t, size_and_event_list_t> chunk_size{};
    uint64_t min_ts = all_events[0].timestamp;
    uint64_t max_ts = all_events[num_events - 1].timestamp;
    uint64_t quarter_ts = (max_ts - min_ts) / 4;
    char quarter_num = 1;
    std::unordered_set<uintptr_t> last_alloc{};
    for (size_t i = 0; i < num_events; i++) {
        auto event = all_events[i];
        if (event.timestamp >= min_ts + (quarter_num*quarter_ts) || (quarter_num <= 4 && event.timestamp == max_ts)) {
            double numerator = 0.0;
            double denominator = 0.0;
            for (auto& chunk: chunk_map) {
                size_t curr_occ = 0;
                for (auto& ev: chunk.second)
                    curr_occ += ev.second;
                if (curr_occ > 0) {
                    numerator += curr_occ;
                    denominator += 1.0;
                }
            }
            numerator /= (double)frag_gran;
            printf("Space usage after Q%d: %f%%\n", quarter_num, 100*(numerator / denominator));
            quarter_num++;
        }

        file_and_line_num_t event_info{event.file, event.line};
        if (include_allocs.size() == 0 ||
            include_allocs.find(event.file) == include_allocs.end() ||
            include_allocs[event.file].find(event.line) == include_allocs[event.file].end()) {
            continue;
        }
        if (include_allocs.size() > 0) {
            auto curr_interval = event_interval_info[event].container;
            bool skip_event = false;
            while (curr_interval != nullptr) {
                if (include_allocs.find(curr_interval->alloc_info->file) != include_allocs.end() &&
                    include_allocs[curr_interval->alloc_info->file].find(curr_interval->alloc_info->line) != include_allocs[curr_interval->alloc_info->file].end()) {
                    skip_event = true;
                    break;
                }
            }
            if (skip_event)
                continue;
        }

        for (auto& addr_sz : split_event(event, frag_gran)) {
            uintptr_t sp_event_addr = addr_sz.first;
            uintptr_t chunk_num = sp_event_addr / frag_gran;
            
            if (chunk_map.find(chunk_num) == chunk_map.end()) {
                chunk_map.insert(std::pair<uintptr_t, std::map<uintptr_t, size_t>>
                    {chunk_num, std::map<uintptr_t, size_t>{}});
                chunk_size.insert(std::pair<uintptr_t, size_and_event_list_t>
                    {chunk_num, size_and_event_list_t{}});
            }

            if (event.typeofop) {
                chunk_map[chunk_num].insert(std::pair<uintptr_t, size_t>{
                    event.timestamp, addr_sz.second
                });
                chunk_size[chunk_num].size += addr_sz.second;
                last_alloc.insert(sp_event_addr);
            }
            else if (last_alloc.find(sp_event_addr) != last_alloc.end()) {
                chunk_map[chunk_num].insert(std::pair<uintptr_t, size_t>{
                    event.timestamp, -addr_sz.second
                });
                chunk_size[chunk_num].size -= addr_sz.second;
            }
            else {
                continue; // TODO could this be break instead of continue?
            }

            chunk_size[chunk_num].events.push_back(addr_sz);

            if (chunk_size[chunk_num].size > frag_gran) {
                std::cout << "BAD CHUNK num = " << chunk_num << std::endl;
                std::cout << "total size: " << chunk_size[chunk_num].size << std::endl;
                for (auto& addr_sz: chunk_size[chunk_num].events) {
                    printf("Event - addr: %lux, size: %lu\n", addr_sz.first, addr_sz.second);
                }
                exit(1);
            }
        }
    }

    double numerator = 0.0, denominator = 0.0;
    for (auto& chunk : chunk_map) {
        uint64_t curr_time = 0, occ_time = 0;
        std::unordered_map<size_t, uint64_t> occ_to_time{};
        size_t curr_occ = 0;

        for (auto& ev: chunk.second) { // ev.first = timestamp, ev.second = change in size
            if (curr_occ > 0) {
                if (occ_to_time.find(curr_occ) == occ_to_time.end())
                occ_to_time.insert(std::pair<size_t, uint64_t>{curr_occ, 0});
                occ_to_time[curr_occ] += ev.first - curr_time;
                occ_time += ev.first - curr_time;
            }
            curr_occ += ev.second;
            assert(curr_occ <= frag_gran);
            curr_time = ev.first;
        }

        double chunk_eff = 0.0;
        for (auto& occ: occ_to_time) {
            double prop_full = (double) occ.first / (double) frag_gran;
            double prop_time = (double) occ.second / 1000000.0;
            chunk_eff += prop_full * prop_time;
        }

        double occ_sec = ((double) occ_time / 1000000.0);     // convert ns to s
        numerator += chunk_eff;
        denominator += occ_sec;
    }

    printf("Average space usage: %f%%\n", 100*(numerator / denominator));
}
