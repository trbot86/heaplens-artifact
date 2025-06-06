#include "io_handler.hpp"

/*
    SUPERTABLE x: contains all of the sampled memory events
    PERF x: contains information about addresses recorded by perf c2c
    FIELDS x: contains information about object fields
    STATS x: contains # allocations and pages for each type
    ALIGNMENT x: contains # allocations for each alignment, size, and type
    LINES x: contains all of the line information for the memory consumption graph
*/
IOHandler::IOHandler() :    zErrMsg{0},
                            in_filename{"binary_dump.txt"},
                            out_filename{"allocs.sqlite"},
                            types_filename{"typeset_dump.txt"},
                            files_filename{"fileset_dump.txt"},
                            frag_filename{"frag_includes.txt"},
                            event_interval_info{},
                            rev_file_map{} {
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

void IOHandler::free_all_descendants(std::vector<memory_event_t>& event_list, 
    std::set<mem_interval_t*, std::function<bool (mem_interval_t*, mem_interval_t*)>>& alloc_intervals,
    uint64_t ts,
    mem_interval_t* node,
    bool add_event) {
    for (auto& child : node->contained) {
        free_all_descendants(event_list, alloc_intervals, ts, child);
    }
    alloc_intervals.erase(node);
    if (add_event) {
        event_list.push_back(memory_event_t{
            node->alloc_info->file,
            node->alloc_info->tindex_name,
            node->alloc_info->line,
            ts,
            node->alloc_info->size,
            node->alloc_info->addr,
            false
        });
    }
}

void IOHandler::sort_and_add_overlap_frees(std::vector<memory_event_t>& event_list) {
    printf("About to do first sort\n");
    std::sort(event_list.begin(), event_list.end(), 
        [](memory_event_t& a, memory_event_t& b) { return a.timestamp < b.timestamp; });

    printf("done first sort\n");

    std::function<bool (mem_interval_t*, mem_interval_t*)> comp = 
        [](mem_interval_t* a, mem_interval_t* b) -> bool {
            return a->start < b->start || (a->start == b->start && a->end < b->end);
        };
    auto alloc_intervals = std::set<mem_interval_t*, decltype(comp)>{comp};
    size_t init_event_list_size = event_list.size();
    for (int i = 0; i < init_event_list_size; i++) {
        uintptr_t event_addr = reinterpret_cast<uintptr_t>(event_list[i].addr);
        mem_interval_t* event_interval = new mem_interval_t{
            event_addr,
            event_addr + reinterpret_cast<uintptr_t>(event_list[i].size),
            nullptr,
            std::unordered_set<mem_interval_t*>{},
            &event_list[i]
        };
        if (event_list[i].typeofop) {
            event_interval_info.insert(std::pair{event_list[i], 
                                                *event_interval});
            auto it = alloc_intervals.lower_bound(event_interval);
            bool continue_searching = false;
            if (it != alloc_intervals.end())
                it++;
            do {
                if (it != alloc_intervals.begin())
                    it--;
                mem_interval_t* other_interval = *it;
                continue_searching = false;

                while (other_interval != nullptr) {
                    if (other_interval->contains(event_interval) == Overlap::Contains) {
                        other_interval->contained.insert(event_interval);
                        event_interval->container = other_interval;
                        break;
                    }
                    else if (other_interval->contains(event_interval) == Overlap::Overwritten) {
                        free_all_descendants(event_list, alloc_intervals,
                                            event_list[i].timestamp, other_interval);
                        it = alloc_intervals.lower_bound(event_interval);
                        if (it == alloc_intervals.end())
                            it--;
                        other_interval = *it;
                        continue_searching = true;
                    }
                    // else if (event_end <= other_addr) {
                    //     continue_searching = true;
                    // }
                    if (it != alloc_intervals.end() && other_interval != nullptr)
                        other_interval = other_interval->container;
                }
            } while (it != alloc_intervals.begin() && continue_searching);

            alloc_intervals.insert(event_interval);
        }
        else {
            free_all_descendants(event_list, alloc_intervals, event_list[i].timestamp,
                                event_interval, false);
        }

        if (event_list.size() % 1000000 == 0) {
            printf("Size of event_list: %lu\n", event_list.size());
            printf("Size of event_interval_info: %lu\n", event_interval_info.size());
            printf("Size of alloc_intervals: %lu\n", alloc_intervals.size());
        }
    }

    printf("done processing events\n");

    std::sort(event_list.begin(), event_list.end(), 
        [](memory_event_t& a, memory_event_t& b) { return a.timestamp < b.timestamp; });
    printf("done second sort\n");
}

std::vector<memory_event_t> IOHandler::get_all_events() {
    FILE* input_file = fopen(in_filename.c_str(), "r");
    if (input_file ==  NULL) {
        std::cout << in_filename << " not found" << std::endl;
        exit(-1);
	}

    struct stat sb;
	fstat(fileno(input_file), &sb);
    long int num_structs = sb.st_size / sizeof(memory_event_t);
    printf("Number of structs in file: %ld\n", num_structs);
    memory_event_t* filemap = reinterpret_cast<memory_event_t*>(
        mmap(NULL, sb.st_size, PROT_READ, MAP_SHARED, fileno(input_file), 0));
    if (filemap == MAP_FAILED) {
        std::cout << "Failed to map input file to memory" << std::endl;
        exit(-1);
    }

    std::vector<memory_event_t> event_list{};
    std::unordered_map<uintptr_t, memory_event_t*> last_alloc{};
    for (int i = 0; i < num_structs; i++) {
        memory_event_t* event = filemap + i;
        uintptr_t event_addr = reinterpret_cast<uintptr_t>(event->addr);
        if (event->typeofop) {
            last_alloc[event_addr] = event;
            event_list.push_back(*event);
        }
        else if (last_alloc.find(event_addr) != last_alloc.end()) {
            event_list.push_back(memory_event_t{
                event->file,
                last_alloc[event_addr]->tindex_name,
                event->line,
                event->timestamp,
                last_alloc[event_addr]->size,
                event->addr,
                event->typeofop
            });
            last_alloc.erase(event_addr);
        }
    }

    sort_and_add_overlap_frees(event_list);
    return event_list;
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