#include "io_handler.hpp"

/*
    SUPERTABLE x: contains all of the sampled memory events
    PERF x: contains information about addresses recorded by perf c2c
    FIELDS x: contains information about object fields
    STATS x: contains # allocations and pages for each type
    ALIGNMENT x: contains # allocations for each alignment, size, and type
    LINES x: contains all of the line information for the memory consumption graph
*/
IOHandler::IOHandler(std::string in_fname, std::string ts_fname, std::string fs_fname,
                    std::string frag_fname, std::string out_fname) :
                            zErrMsg{0},
                            in_filename{in_fname},
                            out_filename{out_fname},
                            types_filename{ts_fname},
                            files_filename{fs_fname},
                            frag_filename{frag_fname},
                            event_interval_info{},
                            rev_file_map{} {
    
    input_file = fopen(in_filename.c_str(), "r+");
    if (input_file ==  NULL) {
        std::cout << in_filename << " not found or permissions insufficient" << std::endl;
        exit(-1);
	}

    struct stat sb;
	fstat(fileno(input_file), &sb);
    input_file_bytes = sb.st_size;
    size_t num_structs = input_file_bytes / sizeof(memory_event_t);
    printf("Number of structs in file: %lu\n", num_structs);

    if (ftruncate(fileno(input_file), 2*input_file_bytes) != 0) {
        printf("Failed to expand input file: %s\n", strerror(errno));
        exit(-1);
    }
    filemap = reinterpret_cast<memory_event_t*>(
        mmap(NULL, 2*input_file_bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE, fileno(input_file), 0));

    if (filemap == MAP_FAILED) {
        printf("Failed to map input file to memory\n");
        exit(-1);
    }
    else {
        printf("Successfully mapped input file\n");
    }
    
    int rc = sqlite3_open("allocs.sqlite", &db);
    if (rc) {
        std::cout << "Can't open database allocs.sqlite: " << sqlite3_errstr(rc) << std::endl;
        exit(-1);
    }

    rc = sqlite3_exec(db, "DROP TABLE IF EXISTS SUPERTABLE;" \
                            "CREATE TABLE SUPERTABLE(" \
                            "FILE       CHAR(100)," \
                            "LINE       INT NOT NULL," \
                            "TIMESTAMP  INT NOT NULL," \
                            "SIZE       INT," \
                            "ACTUALADDR INT," \
                            "ADDRESS    INT NOT NULL," \
                            "isNew      INT," \
                            "TYPE       CHAR(500));", nullptr, 0, &zErrMsg);
    if (rc != SQLITE_OK) {
        std::cout << "SQL error creating SUPERTABLE: " << zErrMsg << std::endl;
        exit(-1);
    }

    rc = sqlite3_exec(db, "DROP TABLE IF EXISTS PERF;" \
                            "CREATE TABLE PERF(" \
                            "CLADDRESS  INT NOT NULL," \
                            "HITM       FLOAT NOT NULL," \
                            "LOADS      INT NOT NULL," \
                            "STORES     INT NOT NULL);", nullptr, 0, &zErrMsg);

    if (rc != SQLITE_OK) {
        std::cout << "SQL error creating PERF table: " << zErrMsg << std::endl;
        exit(-1);
    }

    rc = sqlite3_exec(db, "DROP TABLE IF EXISTS FIELDS;" \
                            "CREATE TABLE FIELDS(" \
                            "TYPE       CHAR(500) NOT NULL," \
                            "SUBTYPE    CHAR(400) NOT NULL," \
                            "NAME       CHAR(100) NOT NULL," \
                            "SIZE       INT NOT NULL," \
                            "OFFSET     INT NOT NULL);", nullptr, 0, &zErrMsg);

    if (rc != SQLITE_OK) {
        std::cout << "SQL error creating FIELDS table: " << zErrMsg << std::endl;
        exit(-1);
    }

    rc = sqlite3_exec(db, "DROP TABLE IF EXISTS STATS;" \
                            "CREATE TABLE STATS(" \
                            "TYPE       CHAR(500) NOT NULL," \
                            "ALLOCS     INT NOT NULL," \
                            "PAGES      INT NOT NULL);", nullptr, 0, &zErrMsg);

    if (rc != SQLITE_OK) {
        std::cout << "SQL error creating STATS table: " << zErrMsg << std::endl;
        exit(-1);
    }

    rc = sqlite3_exec(db, "DROP TABLE IF EXISTS ALIGNMENT;" \
                            "CREATE TABLE ALIGNMENT(" \
                            "TYPE       CHAR(500) NOT NULL," \
                            "ALIGN      INT NOT NULL," \
                            "SIZE       INT NOT NULL," \
                            "COUNT      INT NOT NULL);", nullptr, 0, &zErrMsg);
  
    if (rc != SQLITE_OK) {
        std::cout << "SQL error creating ALIGNMENT table: " << zErrMsg << std::endl;
        exit(-1);
    }

    rc = sqlite3_exec(db, "DROP TABLE IF EXISTS LINES;" \
                            "CREATE TABLE LINES(" \
                            "TYPE       CHAR(500) NOT NULL," \
                            "BUCKET     INT NOT NULL," \
                            "SIZE       INT NOT NULL);", nullptr, 0, &zErrMsg);
    if (rc != SQLITE_OK) {
        std::cout << "SQL error creating LINES table: " << zErrMsg << std::endl;
        exit(-1);
    }

    file_map = construct_map(files_filename);
    type_map = construct_map(types_filename, true);

    for (auto& file_ptr_and_name : file_map) {
        rev_file_map.insert(std::pair<std::string, uintptr_t>{
            file_ptr_and_name.second,
            file_ptr_and_name.first
        });
    }
}

IOHandler::~IOHandler() {
    munmap(filemap, 2*input_file_bytes);
    if (ftruncate(fileno(input_file), input_file_bytes) != 0) {
        printf("Failed to shrink input file: %s\n", strerror(errno));
        exit(-1);
    }
    fclose(input_file);

    sqlite3_free(zErrMsg);
    sqlite3_close(db);
}

std::unordered_map<uintptr_t, std::string> IOHandler::construct_map(std::string filename, 
        bool remove_volatile) {
    std::unordered_map<uintptr_t, std::string> retmap{};
    std::ifstream fd{filename.c_str()};
    std::string val;
    for (std::string key; getline(fd, key, '|'); ) {
        getline(fd, val);
        if (remove_volatile && val.length() >= 8 && val.substr(0, 8) == "volatile")
            val = val.substr(9);

        uintptr_t ptr = (uintptr_t) stoul(key, nullptr, 16);
        retmap.insert(std::pair<uintptr_t, std::string>{ptr, val});
    }
    return retmap;
}

void IOHandler::free_all_descendants(memory_event_t* event_list, 
    std::set<mem_interval_t*, std::function<bool (mem_interval_t*, mem_interval_t*)>>& alloc_intervals,
    uint64_t ts,
    mem_interval_t* node,
    size_t& num_events,
    bool add_event) {

    printf("Here is address of event for free_all_des: %p\n", node->alloc_info->addr);
    printf("Size of node->contained: %lu\n", node->contained.size());

    for (auto& child : node->contained) {
        printf("\tstart addr of child: %lx\n", child->start);
        free_all_descendants(event_list, alloc_intervals, ts, child, num_events);
    }
    size_t size_pre = alloc_intervals.size();
    if (alloc_intervals.erase(node) == 1) {
        if (size_pre != alloc_intervals.size() + 1) {
            printf("find(node) = set.end()? %d\n", alloc_intervals.find(node) == alloc_intervals.end());
            printf("Here is size pre: %lu, here is size post: %lu\n", size_pre, alloc_intervals.size());
        }
        assert(size_pre == alloc_intervals.size() + 1);
        if (add_event) {
            event_list[num_events] = memory_event_t{
                node->alloc_info->file,
                node->alloc_info->tindex_name,
                node->alloc_info->line,
                ts,
                node->alloc_info->size,
                node->alloc_info->addr,
                false
            };
            num_events++;
        }
    }
}

mem_interval_t* get_latest_start(mem_interval_t* node) {
    if (node->contained.size() == 0) {
        return node;
    }

    mem_interval_t* latest = node;
    for (auto child : node->contained) {
        mem_interval_t* other = get_latest_start(child);
        latest = (other->start >= latest->start ? other : latest);
    }
    return latest;
}

size_t IOHandler::sort_and_add_overlap_frees(memory_event_t* event_list, size_t num_events, bool use_container) {
    // Order object intervals first by start address (ASC), then by end address (DES)
    std::function<bool (mem_interval_t*, mem_interval_t*)> comp = 
        [](mem_interval_t* a, mem_interval_t* b) -> bool {
            return a->start < b->start || (a->start == b->start && a->end > b->end);
        };
    auto alloc_intervals = std::set<mem_interval_t*, decltype(comp)>{comp};
    // auto addr_to_size_to_alloc_interval = std::unordered_map<uintptr_t,
    //                                                         std::unordered_map<std::size_t, mem_interval_t*>>{};
    // size_t init_event_list_size = event_list.size();
    size_t init_num_events = num_events;
    size_t num_allocs = 0, num_frees = 0;

    for (size_t i = 0; i < init_num_events; i++) {
        // printf("Here is i: %lu, num_allocs: %lu, num_frees: %lu\n", i, num_allocs, num_frees);
        // printf("\t size of alloc_intervals: %lu\n", alloc_intervals.size());

        uintptr_t event_addr = reinterpret_cast<uintptr_t>(event_list[i].addr);
        mem_interval_t* event_interval = new mem_interval_t{
            event_addr,
            event_addr + reinterpret_cast<uintptr_t>(event_list[i].size),
            nullptr,
            std::unordered_set<mem_interval_t*>{},
            &(event_list[i]),
            i
        };

        if (event_list[i].typeofop) {
            // if (addr_to_size_to_alloc_interval.find(event_addr) == addr_to_size_to_alloc_interval.end()) {
            //     addr_to_size_to_alloc_interval[event_addr] = std::unordered_map<std::size_t, mem_interval_t*>{};
            // }
            // if (addr_to_size_to_alloc_interval[event_addr].find(event_list[i].size) == addr_to_size_to_alloc_interval[event_addr].end()) {
            //     addr_to_size_to_alloc_interval[event_addr][event_list[i].size] = event_interval;
            // }

            num_allocs++;
            event_interval_info.insert({event_list[i], *event_interval});
            if (alloc_intervals.size() > 0) {

                /*  Get the latest-starting interval that starts before 
                    event_interval ends. */
                auto saved_start = event_interval->start;
                event_interval->start = event_interval->end;
                auto it = alloc_intervals.lower_bound(event_interval);
                it--;
                event_interval->start = saved_start;

                auto first_del = alloc_intervals.end();
                auto last_del = alloc_intervals.end();
                bool found_container = false;

                // if (it == alloc_intervals.end())
                //     it--;

                printf("searching on event with addr %p, start %lx, end %lx\n", event_list[i].addr, event_interval->start, event_interval->end);
                printf("here is lower bound addr: %p start %lx end %lx\n", (*it)->alloc_info->addr, (*it)->start, (*it)->end);
                
                mem_interval_t* other_interval = *it;
                Overlap contains_result = other_interval->contains(event_interval);

                printf("contains result: %s\n", contains_result == Overlap::None ? "None" :
                                                contains_result == Overlap::Contains ? "Contains" :
                                                "Overwritten");

                /*  If this event overwrites other_interval, we find the latest starting
                    time among other_interval's descendants and assign the corresponding
                    interval to last_del. This way, we can remove all of the overwritten
                    events in a single call to erase. */
                if (contains_result == Overlap::Overwritten) {
                    first_del = it;
                    mem_interval_t* latest_starter = get_latest_start(other_interval);
                    last_del = alloc_intervals.find(latest_starter);
                    assert(last_del != alloc_intervals.end());
                }

                while (contains_result != Overlap::None ||
                        other_interval->start >= event_interval->end) {
                    
                    printf("\t checking cont for event at addr %p\n", event_list[i].addr);
                    if (use_container && contains_result == Overlap::Contains) {
                        printf("\t\t container found at addr %p!\n", other_interval->alloc_info->addr);
                        other_interval->contained.insert(event_interval);
                        event_interval->container = other_interval;
                        found_container = true;
                        break;
                    }
                    else {
                        printf("\t\t no container - adding to del list\n");
                        if (last_del == alloc_intervals.end()) {
                            first_del = last_del = it;
                            // last_del++;
                        }
                        else {
                            first_del = it;
                        }
                    }

                    if (it == alloc_intervals.begin())
                        break;

                    it--;
                    other_interval = *it;
                    contains_result = other_interval->contains(event_interval);
                }

                if (use_container && !found_container) {
                    printf("\tentering rise loop\n");
                    mem_interval* top_del_interval = nullptr;
                    while (other_interval != nullptr) {
                        contains_result = other_interval->contains(event_interval);
                        if (contains_result == Overlap::Contains) {
                            other_interval->contained.insert(event_interval);
                            event_interval->container = other_interval;
                            found_container = true;
                            printf("\t\t container2 found at addr %p!\n", other_interval->alloc_info->addr);
                            break;
                        }
                        else if (contains_result == Overlap::Overwritten) {
                            top_del_interval = other_interval;
                        }
                        other_interval = other_interval->container;
                    }
                    if (top_del_interval != nullptr) {
                        free_all_descendants(event_list, alloc_intervals, event_list[i].timestamp,
                                            top_del_interval, num_events);
                    }
                }

                size_t size_alloc_intervals_pre = alloc_intervals.size();
                size_t num_events_pre = num_events;
                auto first_del_copy = first_del;
                printf("Set first_del_copy = %p, about to check last_del\n", *first_del_copy);
                if (last_del != alloc_intervals.end()) {
                    last_del++;
                    do {
                        event_list[num_events] = memory_event_t{
                            (*first_del)->alloc_info->file,
                            (*first_del)->alloc_info->tindex_name,
                            (*first_del)->alloc_info->line,
                            event_list[i].timestamp,
                            (*first_del)->alloc_info->size,
                            (*first_del)->alloc_info->addr,
                            false
                        };
                        num_events++;
                        if ((*first_del)->container) {
                            int num_erased = (*first_del)->container->contained.erase(*first_del);
                            assert(num_erased == 1);
                        }
                        first_del++;
                    } while (first_del != last_del);
                    
                    printf("Erasing from %p\n", *first_del_copy);
                    alloc_intervals.erase(first_del_copy, last_del);
                }
                else printf("LAST DEL IS END - BAD\n");
                size_t num_events_post = num_events;
                // if (size_alloc_intervals_pre - (num_events_post - num_events_pre) != alloc_intervals.size()) {
                //     printf("Size before: %lu, elems removed: %lu, diff: %lu, actual size: %lu\n", size_alloc_intervals_pre,
                //                                                                                 num_events_post - num_events_pre,
                //                                                                                 size_alloc_intervals_pre - (num_events_post - num_events_pre),
                //                                                                                 alloc_intervals.size());
                // }
                assert(size_alloc_intervals_pre - (num_events_post - num_events_pre) == alloc_intervals.size());
            }

            size_t size_alloc_intervals_pre_insert = alloc_intervals.size();
            alloc_intervals.insert(event_interval);
            assert(size_alloc_intervals_pre_insert + 1 == alloc_intervals.size());
        }
        else {
            num_frees++;
            printf("processing free event addr %p\n", event_list[i].addr);
            // if (addr_to_size_to_alloc_interval.find(event_addr) == addr_to_size_to_alloc_interval.end() ||
            //     addr_to_size_to_alloc_interval[event_addr].find(event_list[i].size) == addr_to_size_to_alloc_interval[event_addr].end()) {
            //     printf("\t failed to find matching alloc interval\n");
            //     continue;
            // }

            // auto event_interval = addr_to_size_to_alloc_interval[event_addr][event_list[i].size];
            auto first_del = alloc_intervals.find(event_interval);
            if (first_del == alloc_intervals.end()) {
                printf("\t failed to find matching alloc interval\n");
                continue;
            }
            if ((*first_del)->container) {
                int num_erased = (*first_del)->container->contained.erase(*first_del);
                assert(num_erased == 1);
            }

            mem_interval_t* latest_starter = get_latest_start(event_interval);
            auto last_del = alloc_intervals.find(latest_starter);
            assert(last_del != alloc_intervals.end());

            // TODO avoid repeating this part from alloc case
            auto first_del_copy = first_del;
            last_del++;
            do {
                event_list[num_events] = memory_event_t{
                    (*first_del)->alloc_info->file,
                    (*first_del)->alloc_info->tindex_name,
                    (*first_del)->alloc_info->line,
                    event_list[i].timestamp,
                    (*first_del)->alloc_info->size,
                    (*first_del)->alloc_info->addr,
                    false
                };
                num_events++;
                first_del++;
            } while (first_del != last_del);
            
            printf("Erasing from %p\n", *first_del_copy);
            alloc_intervals.erase(first_del_copy, last_del);
            
            // free_all_descendants(event_list, alloc_intervals, event_list[i].timestamp,
            //                     event_interval, num_events, false);
            if (event_interval->container) {
                int num_erased = event_interval->container->contained.erase(event_interval);
                assert(num_erased == 1);
            }
        }
    }

    printf("done processing events\n");

    std::sort(std::execution::par, event_list, event_list + num_events, 
        [](const memory_event_t a, const memory_event_t b) { return a.timestamp < b.timestamp; });
    printf("done second sort\n");

    return num_events;
}

std::pair<memory_event_t*, size_t> IOHandler::get_all_events(bool use_container) {
    printf("About to do first sort\n");
    std::sort(std::execution::par, filemap, filemap + (input_file_bytes / sizeof(memory_event_t)), 
        [](const memory_event_t a, const memory_event_t b) { return a.timestamp < b.timestamp; });
    printf("done first sort\n");

    printf("AAAAAAAAAAAAA HERE ARE ALL EVENTS AAAAAAAAAAA\n");
    // std::vector<memory_event_t> event_list{};
    std::unordered_map<uintptr_t, memory_event_t*> last_alloc{};
    for (int i = 0; i < input_file_bytes / sizeof(memory_event_t); i++) {
        memory_event_t* event = filemap + i;
        uintptr_t event_addr = reinterpret_cast<uintptr_t>(event->addr);

        printf("\t event dets: addr: %lx, size: %lu, tindex: %p\n", event_addr, event->size, event->tindex_name);

        if (event->typeofop) {
            if (last_alloc.find(event_addr) == last_alloc.end())
                last_alloc[event_addr] = event;
            // event_list.push_back(*event);
        }
        else {
            if (last_alloc.find(event_addr) != last_alloc.end()) {
                printf("FOUND matching alloc for addr %p\n", event->addr);
                event->file = last_alloc[event_addr]->file;
                event->line = last_alloc[event_addr]->line;
                event->tindex_name = last_alloc[event_addr]->tindex_name;
                event->size = last_alloc[event_addr]->size;
                last_alloc.erase(event_addr);
                // event_list.push_back(memory_event_t{
                //     event->file,
                //     last_alloc[event_addr]->tindex_name,
                //     event->line,
                //     event->timestamp,
                //     last_alloc[event_addr]->size,
                //     event->addr,
                //     event->typeofop
                // });
                // last_alloc.erase(event_addr);
            }
            else {
                printf("could not find matching alloc for addr %p\n", event->addr);
            }
        }
    }

    size_t new_size = sort_and_add_overlap_frees(filemap,
                                                input_file_bytes / sizeof(memory_event_t),
                                                use_container);
    return std::pair<memory_event_t*, size_t>{filemap, new_size};
    // return event_list;
}

std::unordered_map<memory_event_t, mem_interval_t> IOHandler::get_event_interval_info() {
    return event_interval_info;
}

std::unordered_map<uintptr_t, std::unordered_map<uintptr_t, perf_data_t>>
    IOHandler::get_perf_addrs(std::string perf_filename, size_t page_size, size_t cl_size,
        double cutoff) {
    std::unordered_map<uintptr_t, std::unordered_map<uintptr_t, perf_data_t>> perf_pages{};
    std::ifstream pfile;
    pfile.open(perf_filename);
    std::string line;
    std::cmatch matches;
    std::regex rgx("\\s*[0-9]+\\s+(0x[a-f0-9]+)\\s+\\S+\\s+[0-9]+\\s+([0-9]+\\.[0-9]+)%\\s+[0-9]+\\s+[0-9]+\\s+[0-9]+\\s+[0-9]+\\s+([0-9]+)\\s+([0-9]+)");
    if (pfile.good()) {
        while(getline(pfile, line)) {
            if (regex_search(line.c_str(), matches, rgx)) {
                // printf("Here is the matching perf line: %s\n", line.c_str());
                double hitm = stof(matches[2].str());
                size_t loads = stoul(matches[3].str());
                size_t stores = stoul(matches[4].str());

                uintptr_t cl_addr = strtoull(matches[1].str().c_str(), nullptr, 16);
                // uintptr_t page_addr = cl_addr - (cl_addr % page_size);
                uintptr_t page_num = cl_addr / page_size; // TODO make sure you don't need to mult by CLS here
                if (perf_pages.find(page_num) == perf_pages.end()) {
                    perf_pages.insert(std::pair<uintptr_t, std::unordered_map<uintptr_t, perf_data_t>>
                        {page_num, std::unordered_map<uintptr_t, perf_data_t>{}});
                }
                perf_pages[page_num][cl_addr] = perf_data_t{hitm, loads, stores};
            }
            else {
                // printf("Perf line did NOT match: %s\n", line.c_str());
            }
        }
    }
    else {
        std::cout << "Failed to open perf file: " << perf_filename << std::endl;
    }
    return perf_pages;
}

std::unordered_set<file_and_line_num_t> IOHandler::include_frag_allocs() {
    std::unordered_set<file_and_line_num_t> retset{};
    std::ifstream fd{frag_filename};
    std::string line;
    for (std::string file; getline(fd, file, '|'); ) {
        getline(fd, line);
        if (rev_file_map.find(file) == rev_file_map.end())
            continue;
        retset.insert(file_and_line_num_t{
            rev_file_map[file],
            std::stoi(line)
        });
    }
    return retset;
}

std::unordered_map<uintptr_t, std::string> IOHandler::get_type_map() {
    return type_map;
}

void IOHandler::begin_transaction() {
    int rc = sqlite3_exec(db, "BEGIN TRANSACTION;", nullptr, nullptr, nullptr);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error after begin transaction: %s\n", sqlite3_errstr(rc));
        fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
        exit(-1);
    }
}

void IOHandler::end_transaction() {
    int rc = sqlite3_exec(db, "END TRANSACTION;", nullptr, nullptr, nullptr);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error after end transaction: %s\n", sqlite3_errstr(rc));
        fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
        exit(-1);
    }
}

void IOHandler::step_and_clear_bindings(sqlite3_stmt* stmt) {
    int rc = sqlite3_step(stmt);
    if (rc != SQLITE_DONE) {
        fprintf(stderr, "Error when executing SQL statement: %s\n", sqlite3_errstr(rc));
        exit(-1);
    }
    sqlite3_clear_bindings(stmt);
    sqlite3_reset(stmt);
}

void IOHandler::prepare_write_to_supertable(sqlite3_stmt** stmt) {
    int rc = sqlite3_prepare_v2(db, "INSERT INTO SUPERTABLE (FILE,LINE,TIMESTAMP,SIZE,ACTUALADDR,ADDRESS,isNew,TYPE) " \
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?);", -1, stmt, 0);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error after sqlite prepare: %s\n", sqlite3_errstr(rc));
        fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
        exit(-1);
    }
}

void IOHandler::prepare_write_to_fields(sqlite3_stmt** stmt) {
    int rc = sqlite3_prepare_v2(db, "INSERT INTO FIELDS (TYPE,SUBTYPE,NAME,SIZE,OFFSET) " \
        "VALUES (?, ?, ?, ?, ?);", -1, stmt, 0);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error after sqlite prepare: %s\n", sqlite3_errstr(rc));
        fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
        exit(-1);
    }
}

void IOHandler::prepare_write_to_perf(sqlite3_stmt** stmt) {
    // TODO I think the following should be actual address rather than CLADDRESS - 
    // make sure this is consistent with vis program
    int rc = sqlite3_prepare_v2(db, "INSERT INTO PERF (CLADDRESS,HITM,LOADS,STORES) " \
        "VALUES (?, ?, ?, ?);", -1, stmt, 0);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error after sqlite prepare: %s\n", sqlite3_errstr(rc));
        fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
        exit(-1);
    }
}

void IOHandler::prepare_write_to_lines(sqlite3_stmt** stmt) {
    int rc = sqlite3_prepare_v2(db, "INSERT INTO LINES (TYPE,BUCKET,SIZE) " \
        "VALUES (?, ?, ?);", -1, stmt, 0);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error after sqlite prepare: %s\n", sqlite3_errstr(rc));
        fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
        exit(-1);
    }
}

void IOHandler::prepare_write_to_stats(sqlite3_stmt** stmt) {
    int rc = sqlite3_prepare_v2(db, "INSERT INTO STATS (TYPE,ALLOCS,PAGES) " \
        "VALUES (?, ?, ?);", -1, stmt, 0);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error after sqlite prepare: %s\n", sqlite3_errstr(rc));
        fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
        exit(-1);
    }
}

void IOHandler::prepare_write_to_align(sqlite3_stmt** stmt) {
    int rc = sqlite3_prepare_v2(db, "INSERT INTO ALIGNMENT (TYPE,ALIGN,SIZE,COUNT) " \
        "VALUES (?, ?, ?, ?);", -1, stmt, 0);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "Error after sqlite prepare: %s\n", sqlite3_errstr(rc));
        fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
        exit(-1);
    }
}

void IOHandler::write_event_to_db(sqlite3_stmt* stmt, memory_event_t& ev, 
                                uintptr_t actual_addr) {
    if (ev.file && file_map.find(reinterpret_cast<uintptr_t>(ev.file)) == file_map.end()) {
        printf("FAILED to find file %p in file_map\n", ev.file);
        printf("addr: %p, line: %u, timestamp: %lu\n", ev.addr, ev.line, ev.timestamp);
    }
    const char* fname = ev.file ? file_map.at(reinterpret_cast<uintptr_t>(ev.file)).c_str() : "NULL";
    const char* tname = ev.tindex_name ? type_map.at(reinterpret_cast<uintptr_t>(ev.tindex_name)).c_str() : "NULL";
    sqlite3_bind_text(stmt, 1, fname, strlen(fname), SQLITE_STATIC);
    sqlite3_bind_int(stmt, 2, ev.line);
    sqlite3_bind_int64(stmt, 3, ev.timestamp);
    sqlite3_bind_int64(stmt, 4, ev.size);
    sqlite3_bind_int64(stmt, 5, actual_addr);
    sqlite3_bind_int64(stmt, 6, reinterpret_cast<uintptr_t>(ev.addr));
    sqlite3_bind_int(stmt, 7, ev.typeofop);
    sqlite3_bind_text(stmt, 8, tname, strlen(tname), SQLITE_STATIC);
    step_and_clear_bindings(stmt);
}

void IOHandler::write_lines_to_db(std::unordered_map<uintptr_t, std::vector<int64_t>>& buckets) {
    begin_transaction();
    sqlite3_stmt* stmt;
    prepare_write_to_lines(&stmt);

    for (auto& bucket : buckets) {
        auto tindex_name = bucket.first;
        if (type_map.find(tindex_name) == type_map.end())
            continue;
        std::string tname = type_map[tindex_name];

        auto line = bucket.second;
        for (int i = 0; i < line.size(); i++) {
            sqlite3_bind_text(stmt, 1, tname.c_str(), tname.size(), SQLITE_STATIC);
            sqlite3_bind_int64(stmt, 2, i);
            sqlite3_bind_int64(stmt, 3, line[i]);
            step_and_clear_bindings(stmt);
        }
    }

    end_transaction();
}

void IOHandler::write_perf_to_db(sqlite3_stmt* stmt, uintptr_t addr, double hitm,
                                 size_t loads, size_t stores) {
    sqlite3_bind_int64(stmt, 1, addr);
    sqlite3_bind_double(stmt, 2, hitm);
    sqlite3_bind_int64(stmt, 3, loads);
    sqlite3_bind_int64(stmt, 4, stores);
    step_and_clear_bindings(stmt);
}

void IOHandler::write_fields_to_db(std::string field_filename) {
    std::ifstream pfile;
    pfile.open(field_filename.c_str());
    std::string line;
    std::map<std::string, std::map<std::string, field_data_t>> entries{};
    std::smatch matches;
    std::regex rgx("[^\\|]+\\|([^\\|]+)\\|([^\\|]+)::([^\\|:]+)\\|([0-9]+)\\|([0-9]+)");
    begin_transaction();
    sqlite3_stmt* stmt;
    prepare_write_to_fields(&stmt);
    if (pfile.good()) {
        while(getline(pfile, line)) {
            if (regex_search(line, matches, rgx)) {
                std::string type = matches[2].str();
                std::string type_trim = type;
                type_trim.erase(std::remove_if(type_trim.begin(), type_trim.end(), ::isspace), type_trim.end());
                std::string subtype = matches[1].str();
                std::string name = matches[3].str();
                size_t size = strtoull(matches[4].str().c_str(), nullptr, 10);
                size_t offset = strtoull(matches[5].str().c_str(), nullptr, 10);

                if (entries.find(type_trim) == entries.end() || entries[type_trim].find(name) == entries[type_trim].end())
                    entries[type_trim][name] = field_data_t{subtype, size, offset};
            }
        }

        for (auto& tp_entry : entries) {
            auto type = tp_entry.first;
            auto tp_fields = tp_entry.second;
            
            for (auto& field : tp_fields) {
                auto name = field.first;
                auto field_info = field.second;
                sqlite3_bind_text(stmt, 1, type.c_str(), type.size(), SQLITE_STATIC);
                sqlite3_bind_text(stmt, 2, field_info.subtype.c_str(), field_info.subtype.size(), SQLITE_STATIC);
                sqlite3_bind_text(stmt, 3, name.c_str(), name.size(), SQLITE_STATIC);
                sqlite3_bind_int64(stmt, 4, field_info.size);
                sqlite3_bind_int64(stmt, 5, field_info.offset);
                step_and_clear_bindings(stmt);
            }
        }
    }
    else {
        std::cout << "Failed to open field file: " << field_filename << std::endl;
    }
    end_transaction();
}

void IOHandler::write_stat_to_db(sqlite3_stmt* stmt, uintptr_t tindex,
                                size_t num_allocs, size_t num_pages) {
    std::string tname = type_map[tindex];
    sqlite3_bind_text(stmt, 1, tname.c_str(), tname.size(), SQLITE_STATIC);
    sqlite3_bind_int64(stmt, 2, num_allocs);
    sqlite3_bind_int64(stmt, 3, num_pages);
    step_and_clear_bindings(stmt);
}

void IOHandler::write_align_to_db(sqlite3_stmt* stmt, uintptr_t tindex,
                                size_t align, size_t sz, uint64_t count) {
    std::string tname = type_map[tindex];
    sqlite3_bind_text(stmt, 1, tname.c_str(), tname.size(), SQLITE_STATIC);
    sqlite3_bind_int64(stmt, 2, align);
    sqlite3_bind_int64(stmt, 3, sz);
    sqlite3_bind_int64(stmt, 4, count);
    step_and_clear_bindings(stmt);
}