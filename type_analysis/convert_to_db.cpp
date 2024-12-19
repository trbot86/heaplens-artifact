#include <iostream>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <sqlite3.h>
#include <fstream>
#include <map>
#include <unordered_map>
#include <map>
#include <sstream>
#include <cstring>
#include <sys/stat.h>
#include <vector>
#include <unordered_set>
#include <regex>
#include <getopt.h>
#include <string>
#include <thread>
#include <cmath>
#include <climits>

#define PADDING 64
#ifndef STRUCTS_PER_BLOCK
  #define STRUCTS_PER_BLOCK 1000000
#endif
#define MINIMUM_STRUCT_PER_BLOCK 1000000
#define CTD_NOT_SAMPLED 0
#define CTD_SAMPLED_YES 1
#define CTD_SAMPLED_NO 2

using namespace std;

thread_local sqlite3* my_db;
unordered_map<uintptr_t, string> type_map;
unordered_map<uintptr_t, string> file_map;
const int num_classes = 31;
const size_t size_classes [num_classes] = { 8, 16, 32, 48, 64, 80, 96, 128, 192, 224, 256, 320, 384, 512, 640, 768, 1024, 1280, 
                                            1536, 2048, 3584, 8192, 28672, 40960, 81920, 163840, 655360, 917504, 10485760, 20971520, 99999999999};
size_t page_size;

typedef struct stats {
  unsigned int num_allocs;
  unsigned int num_frees;
  unordered_set<uint64_t> resident_pages;
} stats_t;

typedef struct info {
    const char* file;
    const char* tindex_name;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;

    info() : file(nullptr), tindex_name(nullptr), line(0), timestamp(0), size(0), addr(nullptr) {}
    info(const char* f, const char* t, unsigned int l, uint64_t ts, size_t s, void* a, bool tp) :
                file(f),
                tindex_name(t),
                line(l),
                timestamp(ts),
                size(s),
                addr(a),
                typeofop(tp) {}
} info_t;

typedef struct memory_page {
  unordered_set<uintptr_t> included_types;
  vector<info_t*> events;
  bool has_perf_addr;
  char sampled;
  // uint64_t size;
  memory_page() : included_types(unordered_set<uintptr_t>{}), events(vector<info_t*>()), has_perf_addr(false), sampled(CTD_NOT_SAMPLED) {}

  void add_event(info_t* ev) {
    // events.push(new node_t{ev});
    events.push_back(ev);
    // size++;
    if (included_types.find((uintptr_t) ev->tindex_name) == included_types.end())
      included_types.insert((uintptr_t) ev->tindex_name);
  }
  void join(struct memory_page& other) {
    vector<info_t*> new_events = vector<info_t*>();
    new_events.reserve(events.size() + other.events.size());
    new_events.insert(new_events.end(), events.begin(), events.end());
    new_events.insert(new_events.end(), other.events.begin(), other.events.end());
    included_types.insert(other.included_types.begin(), other.included_types.end());
    events = new_events;
    // events.concat(other.events);
  }
} memory_page_t;

struct perf_data {
  uint64_t addr;
  float hitm;
  uint64_t stores;
  uint64_t loads;
};

size_t bin_search(const size_t* arr, size_t x, int begin, int end) {
  if (begin == end)
    return begin;
  int m = (begin + end) / 2;
  if (x <= arr[m]) {
    return bin_search(arr, x, begin, m);
  }
  else {
    return bin_search(arr, x, m+1, end);
  }
}

unordered_map<uintptr_t, string> construct_map(const char* filename, bool remove_volatile=false) {
  unordered_map<uintptr_t, string> retmap{};
  ifstream fd{filename};
  string val;
  for (string key; getline(fd, key, '|'); ) {
    getline(fd, val);
    if (remove_volatile && val.length() >= 8 && val.substr(0, 8) == "volatile") {
      val = val.substr(9);
      // cout << "Trimmed volatile: " << val << endl;
    }
    // else {
    //   cout << "Did not trim " << val << endl;
    // }
    uintptr_t ptr = (uintptr_t) stoul(key, nullptr, 16);
    retmap.insert(pair<uintptr_t, string>{ptr, val});
  }
  return retmap;
}

void get_perf_addrs(const char* fname, float cutoff, int page_size, int cl_size, map<uint64_t, memory_page_t>& pages, sqlite3* db) {
  ifstream pfile;
  pfile.open(fname);
  string line;
  vector<struct perf_data> entries{};
  cmatch matches;
  regex rgx("[0-9]+\\s+(0x[a-f0-9]+)\\s+\\S+\\s+[0-9]+\\s+[0-9]+\\s+([0-9]+\\.[0-9]+)%\\s+[0-9]+\\s+[0-9]+\\s+[0-9]+\\s+([0-9]+)\\s+[0-9]+\\s+[0-9]+\\s+[0-9]+\\s+[0-9]+\\s+[0-9]+\\s+([0-9]+)");
  if (pfile.good()) {
    while(getline(pfile, line)) {
      if (regex_search(line.c_str(), matches, rgx)) {
        float hitm = stof(matches[2].str());
        if (hitm >= cutoff) {
          uint64_t cl_addr = strtoull(matches[1].str().c_str(), nullptr, 16);
          uint64_t page_num = cl_addr / page_size;
          uint64_t stores = stoul(matches[3].str());
          uint64_t loads = stoul(matches[4].str());
          
          if (pages.find(page_num) == pages.end()) {
            std::cout << "Perf page num not present in data: " << page_num << std::endl;
          }
          else {
            pages[page_num].has_perf_addr = true;
          }
          // cout << "PERF ACTUAL PAGE ADDRESS: " << cl_addr / cl_size << endl;
          if (cl_addr < 18446462598732840960) {
            struct perf_data new_entry{cl_addr, hitm, stores, loads};
            entries.push_back(new_entry);
          }
        }
        else
          break;
      }
    }
    char* zErrMsg = 0;
    int rc = sqlite3_exec(db, "DROP TABLE IF EXISTS PERF;" \
                        "CREATE TABLE PERF(" \
                        "CLADDRESS  INT NOT NULL," \
                        "HITM       FLOAT NOT NULL);", nullptr, 0, &zErrMsg);

    if (rc != SQLITE_OK) {
      std::cout << "SQL error creating perf table: " << zErrMsg << std::endl;
      sqlite3_free(zErrMsg);
      exit(-1);
    }
    else {
      std::cout << "Perf table created successfully" << std::endl;
    }

    vector<struct perf_data>::iterator iter;
    char* charmap = (char *) calloc(entries.size(), 400);
    int bytes_copied = 0;
    for (iter = entries.begin(); iter != entries.end(); iter++) {
      bytes_copied += sprintf(charmap + bytes_copied, "INSERT INTO PERF (CLADDRESS, HITM)" \
                                                      "VALUES ('%ld', %f);",
                                                iter->addr,
                                                iter->hitm);
    }

    std::cout << "Done copying perf data to mem" << std::endl;
    sqlite3_exec(db, "BEGIN TRANSACTION;", nullptr, nullptr, nullptr);
    rc = sqlite3_exec(db, charmap, nullptr, 0, &zErrMsg);
    sqlite3_exec(db, "END TRANSACTION;", nullptr, nullptr, nullptr);

    if (rc != SQLITE_OK) {
      std::cout << "SQL error: " << zErrMsg << std::endl;
      sqlite3_free(zErrMsg);
      free(charmap);
      sqlite3_close(db);
      exit(-1);
    }

    std::cout << "Done writing perf table to file" << std::endl;

    free(charmap);
  }
  else {
    std::cout << "Failed to open perf output file " << fname << std::endl;
  }
}

struct field_data {
  string subtype;
  size_t size;
  size_t offset;
};

void get_fields(const char* fname, unordered_set<string> seen_types, sqlite3* db) {
  unordered_set<string>::iterator seeniter;
  for (seeniter = seen_types.begin(); seeniter != seen_types.end(); seeniter++)
    std::cout << *seeniter << std::endl;

  ifstream pfile;
  pfile.open(fname);
  string line;
  map<string, map<string, struct field_data>> entries{};
  smatch matches;
  regex rgx("[^\\|]+\\|([^\\|]+)\\|([^\\|]+)::([^\\|:]+)\\|([0-9]+)\\|([0-9]+)");
  if (pfile.good()) {
    while(getline(pfile, line)) {
      if (regex_search(line, matches, rgx)) {
        // cout << line << endl;
        // cout << matches[0] << endl;
        // cout << "MATCHES SIZE: " << matches.size() << endl;
        string type = matches[2].str();
        string type_trim = type;
        type_trim.erase(std::remove_if(type_trim.begin(), type_trim.end(), ::isspace), type_trim.end());
        string subtype = matches[1].str();
        string name = matches[3].str();
        size_t size = strtoull(matches[4].str().c_str(), nullptr, 10);
        size_t offset = strtoull(matches[5].str().c_str(), nullptr, 10);
        string type_trim_t = type_trim + "_t";

        // if (seen_types.find(type) != seen_types.end())
        //   cout << "Seen types contains type " << type << endl;
        // else
        //   cout << "NO" << type << " " << subtype << " " << name << " " << size << " " << offset << endl;

        if (seen_types.find(type_trim.c_str()) != seen_types.end() &&
            (entries.find(type_trim) == entries.end() || entries[type_trim].find(name) == entries[type_trim].end())) {
          struct field_data new_entry{subtype, size, offset};
          entries[type_trim][name] = new_entry;
        }
        else if (seen_types.find(type_trim_t.c_str()) != seen_types.end() &&
            (entries.find(type_trim_t) == entries.end() || entries[type_trim_t].find(name) == entries[type_trim_t].end())) {
          struct field_data new_entry{subtype, size, offset};
          entries[type_trim_t][name] = new_entry;
        }
      }
    }
    char* zErrMsg = 0;
    int rc = sqlite3_exec(db, "DROP TABLE IF EXISTS FIELDS;" \
                        "CREATE TABLE FIELDS(" \
                        "TYPE       CHAR(500) NOT NULL," \
                        "SUBTYPE    CHAR(400) NOT NULL," \
                        "NAME       CHAR(100) NOT NULL," \
                        "SIZE       INT NOT NULL," \
                        "OFFSET     INT NOT NULL);", nullptr, 0, &zErrMsg);

    if (rc != SQLITE_OK) {
      std::cout << "SQL error creating fields table: " << zErrMsg << std::endl;
      sqlite3_free(zErrMsg);
      exit(-1);
    }
    else {
      std::cout << "Fields table created successfully" << std::endl;
    }

    // cout << "Size of map: " << entries.size() << endl;
    map<string, map<string, struct field_data>>::iterator typeiter;
    char* charmap = (char *) calloc(entries.size(), 1000000);
    int bytes_copied = 0;
    int k = 0;
    for (typeiter = entries.begin(); typeiter != entries.end(); ) {
      string type = typeiter->first;
      map<string, struct field_data> fields = typeiter->second;
      map<string, struct field_data>::iterator fielditer;
      for (fielditer = fields.begin(); fielditer != fields.end(); fielditer++) {
        bytes_copied += sprintf(charmap + bytes_copied, "INSERT INTO FIELDS (TYPE, SUBTYPE, NAME, SIZE, OFFSET)" \
                                                      "VALUES ('%s', '%s', '%s', %ld, %ld);",
                                                type.c_str(),
                                                fielditer->second.subtype.c_str(),
                                                fielditer->first.c_str(),
                                                fielditer->second.size,
                                                fielditer->second.offset);
      }

      k++;
      typeiter++;

      if (typeiter == entries.end() || bytes_copied > 900000) {
        std::cout << "Copied fields data to mem" << std::endl;
        sqlite3_exec(db, "BEGIN TRANSACTION;", nullptr, nullptr, nullptr);
        rc = sqlite3_exec(db, charmap, nullptr, 0, &zErrMsg);
        sqlite3_exec(db, "END TRANSACTION;", nullptr, nullptr, nullptr);

        if (rc != SQLITE_OK) {
          std::cout << "SQL error: " << zErrMsg << std::endl;
          sqlite3_free(zErrMsg);
          free(charmap);
          sqlite3_close(db);
          exit(-1);
        }

        bytes_copied = 0;
        memset(charmap, 0, 1000000);
      }
    }

    std::cout << "Done writing fields table to file" << std::endl;

    free(charmap);
  }
  else {
    std::cout << "Failed to open fields output file " << fname << std::endl;
  }
}

void get_stats(unordered_map<uintptr_t, string>& type_map, unordered_map<uintptr_t, stats_t*>& stats_per_type, sqlite3* db) {
  char* zErrMsg = 0;
  int rc = sqlite3_exec(db, "DROP TABLE IF EXISTS STATS;" \
                      "CREATE TABLE STATS(" \
                      "TYPE       CHAR(500) NOT NULL," \
                      "ALLOCS     INT NOT NULL," \
                      "PAGES      INT NOT NULL);", nullptr, 0, &zErrMsg);

  if (rc != SQLITE_OK) {
    std::cout << "SQL error creating stats table: " << zErrMsg << std::endl;
    sqlite3_free(zErrMsg);
  }
  else {
    std::cout << "Stats table created successfully" << std::endl;
  }

  sqlite3_stmt* stmt = 0;
  rc = sqlite3_prepare_v2(db, "INSERT INTO STATS (TYPE,ALLOCS,PAGES) " \
                              "VALUES (?, ?, ?);", -1, &stmt, 0);

  if (rc != SQLITE_OK) {
    fprintf(stderr, "Error after sqlite prepare: %s\n", sqlite3_errstr(rc));
    fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
  }

  rc = sqlite3_exec(db, "BEGIN TRANSACTION;", nullptr, nullptr, nullptr);

  if (rc != SQLITE_OK) {
    fprintf(stderr, "Error after begin transaction: %s\n", sqlite3_errstr(rc));
    fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
  }

  for (auto& s: stats_per_type) {
    if (type_map.find((uintptr_t) s.first) == type_map.end())
      continue;
    const char* tname = type_map[s.first].c_str();
    // printf("Adding %s to table\n", tname);
    sqlite3_bind_text(stmt, 1, tname, strlen(tname), NULL);
    sqlite3_bind_int(stmt, 2, s.second->num_allocs);
    sqlite3_bind_int(stmt, 3, s.second->resident_pages.size());

    rc = sqlite3_step(stmt);
    if (rc != SQLITE_DONE) {
      fprintf(stderr, "Error creating stats table: %s\n", sqlite3_errstr(rc));
      fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
    }

    // sqlite3_step(stmt);
    sqlite3_clear_bindings(stmt);
    sqlite3_reset(stmt);
  }

  rc = sqlite3_exec(db, "END TRANSACTION;", nullptr, nullptr, nullptr);

  if (rc != SQLITE_OK) {
    std::cout << "SQL error creating stats table: " << sqlite3_errstr(rc) << std::endl;
    // free(charmap);
  }
}

void get_lines(unordered_map<uintptr_t, string>& type_map, unordered_map<uintptr_t, vector<uint64_t>>& all_buckets, size_t buckets, sqlite3* db) {
  char* zErrMsg = 0;
  int rc = sqlite3_exec(db, "DROP TABLE IF EXISTS LINES;" \
                      "CREATE TABLE LINES(" \
                      "TYPE       CHAR(500) NOT NULL," \
                      "BUCKET     INT NOT NULL," \
                      "SIZE       INT NOT NULL);", nullptr, 0, &zErrMsg);

  if (rc != SQLITE_OK) {
    std::cout << "SQL error creating stats table: " << zErrMsg << std::endl;
    sqlite3_free(zErrMsg);
  }
  else {
    std::cout << "Lines table created successfully" << std::endl;
  }

  sqlite3_stmt* stmt = 0;
  rc = sqlite3_prepare_v2(db, "INSERT INTO LINES (TYPE,BUCKET,SIZE) " \
                              "VALUES (?, ?, ?);", -1, &stmt, 0);

  if (rc != SQLITE_OK) {
    fprintf(stderr, "Error after sqlite prepare: %s\n", sqlite3_errstr(rc));
    fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
  }

  rc = sqlite3_exec(db, "BEGIN TRANSACTION;", nullptr, nullptr, nullptr);

  if (rc != SQLITE_OK) {
    fprintf(stderr, "Error after begin transaction: %s\n", sqlite3_errstr(rc));
    fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
  }

  for (auto& it: all_buckets) {
    if (type_map.find((uintptr_t) it.first) == type_map.end())
      continue;
    const char* tname = type_map[it.first].c_str();
    // printf("Adding %s to table\n", tname);
    for (int i = 0; i < buckets + 2; i++) {
      sqlite3_bind_text(stmt, 1, tname, strlen(tname), NULL);
      sqlite3_bind_int64(stmt, 2, i);
      sqlite3_bind_int64(stmt, 3, it.second[i]);

      rc = sqlite3_step(stmt);
      if (rc != SQLITE_DONE) {
        fprintf(stderr, "Error creating lines table: %s\n", sqlite3_errstr(rc));
        fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
      }

      // sqlite3_step(stmt);
      sqlite3_clear_bindings(stmt);
      sqlite3_reset(stmt);
    }
  }

  rc = sqlite3_exec(db, "END TRANSACTION;", nullptr, nullptr, nullptr);

  if (rc != SQLITE_OK) {
    std::cout << "SQL error creating lines table: " << sqlite3_errstr(rc) << std::endl;
  }
}

uint64_t get_bucket(uint64_t ts, size_t num_buckets, uint64_t min_ts, uint64_t max_ts) {
  uint64_t size_of_bucket = std::max((max_ts - min_ts) / num_buckets, (uint64_t) 1);
  return std::ceil(((double) ts - (double) min_ts) / (double) size_of_bucket);
}

void create_supertable(sqlite3* db) {
  char* zErrMsg = 0;
  int rc = sqlite3_exec(db, "DROP TABLE IF EXISTS SUPERTABLE;" \
                        "CREATE TABLE SUPERTABLE(" \
                        "FILE       CHAR(100)," \
                        "LINE       INT NOT NULL," \
                        "TIMESTAMP  INT NOT NULL," \
                        "SIZE       INT," \
                        "ADDRESS    INT NOT NULL," \
                        "isNew      INT," \
                        "TYPE       CHAR(500));", nullptr, 0, &zErrMsg);

  if (rc != SQLITE_OK) {
    cout << "SQL error creating supertable: " << zErrMsg << endl;
    sqlite3_free(zErrMsg);
    exit(-1);
  }
  else {
    cout << "Supertable created successfully" << endl;
  }
}

void sort_events_into_pages(int id, int chunk_size, int start_ind, info_t* filemap, vector<uint64_t>& min_ts,
                        vector<uint64_t>& max_ts, unordered_map<uint64_t, memory_page_t>& pages, unordered_set<uintptr_t>& raw_type_set,
                        unordered_map<size_t, int>& size_class_counts, unordered_map<uintptr_t, stats_t*>& stats_per_type) {
  for (int i = 0; i < chunk_size; i++) {
    info_t* event = filemap + start_ind + i;
    
    if (event->timestamp < min_ts[id]) {
      min_ts[id] = event->timestamp;
    }
    if (event->timestamp > max_ts[id]) {
      max_ts[id] = event->timestamp;
    }

    if (stats_per_type.find((uintptr_t) event->tindex_name) == stats_per_type.end()) {
      // cout << "Adding for type: " << (uintptr_t) event->tindex_name << endl;
      stats_per_type.insert(pair<uintptr_t, stats_t*>{(uintptr_t) event->tindex_name, new stats_t{
                                                                                event->typeofop ? 1u : 0u, // num_allocs
                                                                                event->typeofop ? 0u : 1u, // num_frees
                                                                                unordered_set<uint64_t>{}
                                                                              }});
    }
    else {
      stats_per_type[(uintptr_t) event->tindex_name]->num_allocs++;
      stats_per_type[(uintptr_t) event->tindex_name]->num_frees++;
    }

    uint64_t page_num = (uint64_t)event->addr / page_size;
    if (event->typeofop)
      stats_per_type[(uintptr_t) event->tindex_name]->resident_pages.insert(page_num);
    
    // uint64_t page_num_end = ((uint64_t)event->addr + event->size) / page_size;
    if (pages.find(page_num) == pages.end()) {
      pages.insert(pair<uint64_t, memory_page_t>{page_num, memory_page_t{}});
      // printf("Address of new page: %p\n", &pages[page_num]);
    }
    // if (page_num_end != page_num && pages.find(page_num_end) == pages.end())
    //   pages.insert(pair<uint64_t, memory_page_t>{page_num_end, memory_page_t{}})

    pages[page_num].add_event(event);

    // if (type_map.find((uintptr_t) event->tindex_name) != type_map.end()) {
      // string type_trim = type_map.at((uintptr_t) event->tindex_name);
      // type_trim.erase(std::remove_if(type_trim.begin(), type_trim.end(), ::isspace), type_trim.end());
      // type_set.insert(type_trim);
    if (event->typeofop) {
      raw_type_set.insert((uintptr_t) event->tindex_name);
    }
    // }

    if (event->size > 0) {
      int ind = bin_search(size_classes, event->size, 0, num_classes);
      // if (i % 1000000 == 0)
      //   cout << "Size: " << event->size << " Index: " << ind << " Size class: " << size_classes[ind] << endl;
      size_class_counts[size_classes[ind]] = size_class_counts[size_classes[ind]] + 1;
    }
  }
}

struct size_and_type {
  size_t size;
  uintptr_t type;
};

// TODO: is everything guaranteed to be sorted by timestamp at this point?
// this is important for the use of last_alloc_size and alloc_intervals
void split_events_across_pages( int id, int chunk_size, int start_ind, unordered_map<uint64_t, memory_page_t>& all_pages,
                                vector<uint64_t>& page_num_list, unordered_map<uint64_t, memory_page_t>& pages,
                                uint64_t min_ts, uint64_t max_ts, size_t buckets, unordered_map<uintptr_t, vector<uint64_t>>& thread_buckets,
                                unordered_map<uintptr_t, stats_t*>& stats_per_type) {
  for (int i = start_ind; i < start_ind + chunk_size; i++) {
    uint64_t page_num = page_num_list[i];
    if (pages.find(page_num) == pages.end())
        pages.insert(pair<uint64_t, memory_page_t>{page_num, memory_page_t{}});
    // node_t* n = all_pages[page_num_list[i]].events.head;
    unordered_map<uintptr_t, struct size_and_type> last_alloc_info{};
    map<uintptr_t, uintptr_t> alloc_intervals{};  // all NON-OVERLAPPING intervals currently allocated
    std::sort(all_pages[page_num_list[i]].events.begin(), all_pages[page_num_list[i]].events.end(),
              [](info_t* a, info_t* b){ return a->timestamp < b->timestamp; });
    for (const info_t* event : all_pages[page_num_list[i]].events) {
    // while (n != nullptr) {
      // info_t* event = n->data;
      size_t eventSize = event->typeofop ? event->size : last_alloc_info.find((uintptr_t) event->addr) != last_alloc_info.end() ? last_alloc_info[(uintptr_t) event->addr].size : 0;

      if (event->typeofop) {
        // printf("Here is event addr: %p, eventSize: %lu\n", event->addr, event->size);
        // printf("(alloc) Here is tindex name: %p, here is bucket: %lu\n", event->tindex_name, get_bucket(event->timestamp, buckets, min_ts, max_ts));
        // printf("is tindex_name NULL? %d, typeofop: %d\n", event->tindex_name == NULL, event->typeofop);
        // printf("here is size of vector: %lu\n", thread_buckets[(uintptr_t) event->tindex_name].size());
        thread_buckets[(uintptr_t) event->tindex_name][get_bucket(event->timestamp, buckets, min_ts, max_ts)] += eventSize;
        // printf("About to search for address %p\n", event->addr);
        map<uintptr_t, uintptr_t>::iterator i = alloc_intervals.lower_bound((uintptr_t) event->addr);
        if (i != alloc_intervals.end())
          i++;

        if (alloc_intervals.size() > 0) {
          do {
            if (i != alloc_intervals.begin())
              i--;
            if (i->first <= (uintptr_t) event->addr && i->second > (uintptr_t) event->addr + event->size ||   // event strictly contained inside i
                i->first < (uintptr_t) event->addr && i->second >= (uintptr_t) event->addr + event->size) {
              // remove i, DON'T add free for i
              alloc_intervals.erase(i->first);
              i = alloc_intervals.lower_bound((uintptr_t) event->addr);
              break;
            }
            else if (i->second <= (uintptr_t) event->addr) {   // event is after i
              break;
            }
            else if (i->first < (uintptr_t) event->addr + event->size) {   // event overlaps with i but is not contained within i
              // remove i, add free for i
              pages[page_num].add_event(new info_t(event->file, event->tindex_name, 0, event->timestamp-1, 0, (void*) i->first, false));
              alloc_intervals.erase(i->first);
              i = alloc_intervals.lower_bound((uintptr_t) event->addr);
            }
          } while (i != alloc_intervals.begin());
          // printf("FINISHED THE LOOP\n");
        }
        alloc_intervals.insert(pair<uintptr_t, uintptr_t>{(uintptr_t) event->addr, (uintptr_t) event->addr + event->size});         
        last_alloc_info.insert(pair<uintptr_t, struct size_and_type>{(uintptr_t) event->addr, size_and_type{event->size, (uintptr_t)event->tindex_name}});
      }
      else if (last_alloc_info.find((uintptr_t) event->addr) != last_alloc_info.end()) {
        // printf("(free) Here is tindex name: %lX, here is bucket: %lu\n", last_alloc_info[(uintptr_t) event->addr].type, get_bucket(event->timestamp, buckets, min_ts, max_ts));
        thread_buckets[last_alloc_info[(uintptr_t) event->addr].type][get_bucket(event->timestamp, buckets, min_ts, max_ts)] -= eventSize;
        alloc_intervals.erase((uintptr_t) event->addr);
      }

      if (stats_per_type.find((uintptr_t)event->tindex_name) != stats_per_type.end())
        stats_per_type[(uintptr_t)event->tindex_name]->resident_pages.insert(page_num);
      uint64_t page_num_end = ((uint64_t) event->addr + eventSize - 1) / page_size; // Need to -1 for objects that end on page boundary

      if (page_num != page_num_end) {
        eventSize = page_size - ((uint64_t) event->addr % page_size);
        uint64_t new_event_addr = (uint64_t) event->addr + eventSize;
        int64_t rem_size = event->size - eventSize;
        do {
          uint64_t new_event_page_num = new_event_addr / page_size;
          if (pages.find(new_event_page_num) == pages.end())
            pages.insert(pair<uint64_t, memory_page_t>{new_event_page_num, memory_page_t{}});
          pages[new_event_page_num].add_event(new info_t{ event->file,
                                                          event->tindex_name,
                                                          event->line,
                                                          event->timestamp,
                                                          min((uint64_t)rem_size, page_size),
                                                          (void*) new_event_addr,
                                                          event->typeofop});
          new_event_addr += page_size;
          rem_size -= page_size;
        } while (rem_size > 0);
      }

      pages[page_num].add_event(new info_t{event->file,
                                event->tindex_name,
                                event->line,
                                event->timestamp,
                                eventSize,
                                event->addr,
                                event->typeofop});
      
      // n = n->next;
    }
  }

  for (auto& it: thread_buckets) {
    for (int i = 1; i < buckets+2; i++) {
      it.second[i] += it.second[i-1];
    }
  }
}

void write_event_to_db(sqlite3_stmt* stmt, info_t event) {
  const char* fname = event.file ? file_map.at((uintptr_t) event.file).c_str() : "NULL";
  const char* tname = event.tindex_name ? type_map.at((uintptr_t) event.tindex_name).c_str() : "NULL";
  sqlite3_bind_text(stmt, 1, fname, strlen(fname), NULL);
  sqlite3_bind_int(stmt, 2, event.line);
  sqlite3_bind_int64(stmt, 3, event.timestamp);
  sqlite3_bind_int64(stmt, 4, event.size);
  sqlite3_bind_int64(stmt, 5, (uintptr_t) event.addr);
  sqlite3_bind_int(stmt, 6, event.typeofop);
  sqlite3_bind_text(stmt, 7, tname, strlen(tname), NULL);

  if ((uintptr_t) event.addr == 140576089034810) {
    printf("\tWRITING TO DB: HERE IS THE PROBLEM EVENT\n");
    printf("\ttimestamp: %lu, typeofop: %d\n", event.timestamp, event.typeofop);
  }

  int rc = sqlite3_step(stmt);
  if (rc != SQLITE_DONE) {
    fprintf(stderr, "Error in case 1: %s\n", sqlite3_errstr(rc));
    // fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
    // fclose(input_file);
    // sqlite3_close(db);
    exit(-1);
  } // TODO better error handling

  // sqlite3_step(stmt);
  sqlite3_clear_bindings(stmt);
  sqlite3_reset(stmt);
}



int main(int argc, char* argv[]) {
  struct option long_opts[] = {
    {"perf-file",           required_argument,  0,  'p'},
    {"hitm-cutoff",         required_argument,  0,  'c'},
    {"sample-portion",      required_argument,  0,  's'},
    {"page-size",           required_argument,  0,  0},
    {"cacheline-size",      required_argument,  0,  0},
    {"num-pages-per-type",  required_argument,  0,  't'},
    {"field-dump",          required_argument,  0,  'f'},
    {"malloc-type-c",       required_argument,  0,  'm'},
    {"threads",             optional_argument,  0,  'j'},
    {"buckets",             required_argument,  0,  'b'}
  };
  int opt_ind = 0;

  int c;
  float sample_portion = 1.0;
  float cutoff = 0.0001;
  const char* perf_file;
  bool is_perf_file = false;
  const char* field_file;
  bool is_field_file = false;
  page_size = 4096;
  int cacheline_size = 64;
  int num_pages_per_type = 1;
  unsigned int num_threads = 1;
  const char* type_c_file;
  bool is_type_c = false;
  size_t buckets = 3000;
  while ((c = getopt_long(argc, argv, "p:c:s:t:j:", long_opts, &opt_ind)) != -1) {
    switch (c) {
      case 0:
        switch (opt_ind) {
          case 3:
            page_size = stoi(optarg);
            break;
          case 4:
            cacheline_size = stoi(optarg);
            break;
          default:
            break;
        }
        break;
      case 'p':
        perf_file = optarg;
        is_perf_file = true;
        break;
      case 'c':
        cutoff = stof(optarg);
        break;
      case 's':
        sample_portion = stof(optarg);
        break;
      case 't':
        num_pages_per_type = stoi(optarg);
        break;
      case 'f':
        field_file = optarg;
        is_field_file = true;
        break;
      case 'j':
        if (optarg != NULL)
          num_threads = stoi(optarg);
        else
          num_threads = thread::hardware_concurrency();
      case 'm':
        type_c_file = optarg;
        is_type_c = true;
        break;
      case 'b':
        buckets = stoi(optarg);
        break;
      default:
        break;
    }
  }

  cout << "Sample percent: " << sample_portion << endl;
  cout << "Number of pages per type: " << num_pages_per_type << endl;
  cout << "Number of threads: " << num_threads << endl;

  int rc = sqlite3_config(SQLITE_CONFIG_MULTITHREAD);
  if (rc) {
    cout << "Cannot configure sqlite3: " << sqlite3_errstr(rc) << endl;
    exit(-1);
  }

  sqlite3* db;
  rc = sqlite3_open("allocs.sqlite", &db);

  if (rc) {
    cout << "Can't open database allocs.sqlite: " << sqlite3_errstr(rc) << endl;
    exit(-1);
  }

  unsigned long int file_byte_size = 0;
  struct stat sb;

  FILE* input_file = fopen("binary_dump.txt", "r");
  if (input_file ==  NULL) {
		printf("binary_dump.txt not found\n");
    exit(-1);
	}
	
	fstat(fileno(input_file), &sb);
  file_byte_size = (unsigned long int) sb.st_size;
  long int num_structs = file_byte_size / sizeof(info_t);

  create_supertable(db);
  printf("Number of structs in file: %ld\n", num_structs);
  info_t* filemap = (info_t*) mmap(NULL, file_byte_size, PROT_READ, MAP_SHARED, fileno(input_file), 0);

  if (filemap == MAP_FAILED) {
    cout << "Failed to map input file to memory" << endl;
    exit(-1);
  }

  type_map = construct_map("typeset_dump.txt", true);
  file_map = construct_map("fileset_dump.txt");
  // vector<unordered_map<uintptr_t, unordered_set<uint64_t>>> include_addrs{num_threads, unordered_map};
  // unordered_set<uint64_t> skip_addrs{};
  // vector<unordered_map<uintptr_t, int>> seen_types{num_threads, unordered_map<uintptr_t, int>{}};
  vector<unordered_map<uint64_t, memory_page_t>> pages(num_threads, unordered_map<uint64_t, memory_page_t>{});
  vector<unordered_set<uintptr_t>> raw_type_set(num_threads, unordered_set<uintptr_t>{});
  vector<unordered_set<string>> type_set(num_threads, unordered_set<string>{});
  vector<unordered_map<size_t, int>> size_class_counts(num_threads, unordered_map<size_t, int>{});
  vector<unordered_map<uintptr_t, stats_t*>> stats_per_type(num_threads, unordered_map<uintptr_t, stats_t*>{});
  vector<uint64_t> min_vals(num_threads, ULLONG_MAX);
  vector<uint64_t> max_vals(num_threads, 0);

  for (int t = 0; t < num_threads; t++) {
    for (int i = 0; i < num_classes; i++) {
      size_class_counts[t].insert(pair<size_t, int>{size_classes[i], 0});
    }
  }

  int chunk_size = ceil((double)num_structs / (double)num_threads);
  vector<thread> workers{num_threads};
  map<uint64_t, memory_page_t> all_pages{};
  unordered_map<uintptr_t, int> all_raw_type_count{};
  unordered_set<string> all_type_set{};
  unordered_map<size_t, int> all_size_class_counts{};
  unordered_map<uintptr_t, stats_t*> all_stats_per_type{};
  vector<uint64_t> page_num_list{};
  uint64_t min_all_vals;
  uint64_t max_all_vals;

  cout << "Starting worker threads..." << endl;

  for (int t = 0; t < num_threads; t++) {
    workers[t] = thread(sort_events_into_pages, t, (int) min((long) chunk_size, num_structs - (t*chunk_size)),
                        t*chunk_size, filemap, ref(min_vals), ref(max_vals), ref(pages[t]), ref(raw_type_set[t]),
                        ref(size_class_counts[t]), ref(stats_per_type[t]));
  }
  for (int t = 0; t < num_threads; t++) {
    workers[t].join();
    cout << "Thread " << t << " joined in sort step" << endl;
    for (auto& p: pages[t]) {
      if (all_pages.find(p.first) == all_pages.end()) {
        all_pages[p.first] = p.second;
        page_num_list.push_back(p.first);
      }
      else {
        all_pages[p.first].join(p.second);
      }
    }
    pages[t] = unordered_map<uint64_t, memory_page_t>{};
    for (auto& tp: raw_type_set[t]) {
      all_raw_type_count.insert(pair<uintptr_t, int>{tp, 0});
    }
    for (auto& s: size_class_counts[t]) {
      if (all_size_class_counts.find(s.first) == all_size_class_counts.end()) {
        all_size_class_counts[s.first] = s.second;
      }
      else {
        all_size_class_counts[s.first] += s.second;
      }
    }
    // cout << "Size of stats per type " << t << " : " << stats_per_type[t].size() << endl;
    if (t == 0) {
      min_all_vals = min_vals[t];
      max_all_vals = max_vals[t];
    }
    else {
      min_all_vals = std::min(min_vals[t], min_all_vals);
      max_all_vals = std::max(max_vals[t], max_all_vals);
    }
  }

  cout << "Done sorting step" << endl;
  cout << "Starting split step..." << endl;

  chunk_size = ceil((double)page_num_list.size() / (double)num_threads);
  unordered_map<uint64_t, memory_page_t> split_pages{};
  vector<unordered_map<uintptr_t, vector<uint64_t>>> thread_buckets{num_threads, unordered_map<uintptr_t, vector<uint64_t>>{}};
  unordered_map<uintptr_t, vector<uint64_t>> all_buckets{};
  for (auto& it: all_raw_type_count) {
    all_buckets.insert(pair<uintptr_t, vector<uint64_t>>{it.first, vector<uint64_t>(buckets+2, 0)});
    for (int t = 0; t < num_threads; t++) {
      thread_buckets[t].insert(pair<uintptr_t, vector<uint64_t>>{it.first, vector<uint64_t>(buckets+2, 0)});
    }
  }

  cout << "Num pages: " << page_num_list.size() << " Chunk size: " << chunk_size << endl;

  for (int t = 0; t < num_threads; t++) {
    workers[t] = thread(split_events_across_pages, t, (int) min((long) chunk_size, (long) page_num_list.size() - (t*chunk_size)),
                        t*chunk_size, ref(all_pages), ref(page_num_list), ref(pages[t]), min_all_vals, max_all_vals,
                        buckets, ref(thread_buckets[t]), ref(stats_per_type[t]));
  }
  for (int t = 0; t < num_threads; t++) {
    workers[t].join();
    cout << "Thread " << t << " joined in split step" << endl;
    for (auto& p: pages[t]) {
      if (split_pages.find(p.first) == split_pages.end()) {
        split_pages[p.first] = p.second;
      }
      else {
        split_pages[p.first].join(p.second);
      }
    }
    for (auto& it: all_raw_type_count) {
      for (int i = 0; i < buckets + 2; i++) {
        all_buckets[it.first][i] += thread_buckets[t][it.first][i];
      }
    }
    for (auto& s: stats_per_type[t]) {
      if (all_stats_per_type.find(s.first) == all_stats_per_type.end()) {
        all_stats_per_type[s.first] = s.second;
      }
      else {
        all_stats_per_type[s.first]->num_allocs += s.second->num_allocs;
        all_stats_per_type[s.first]->num_frees += s.second->num_frees;
        all_stats_per_type[s.first]->resident_pages.insert(s.second->resident_pages.begin(), s.second->resident_pages.end());
      }
    }
  }

  cout << "All worker threads joined!" << endl;
  cout << "Size of all stats per type: " << all_stats_per_type.size() << endl;

  for (const auto& tp: all_raw_type_count) {
    if (type_map.find(tp.first) != type_map.end()) {
      string type_trim = type_map.at(tp.first);
      type_trim.erase(std::remove_if(type_trim.begin(), type_trim.end(), ::isspace), type_trim.end());
      all_type_set.insert(type_trim);
    }
  }

  if (is_perf_file)
    get_perf_addrs(perf_file, cutoff, page_size, cacheline_size, all_pages, db);

  cout << "----- SIZE CLASS TABLE -----" << endl;
  for (int i = 0; i < num_classes; i++) {
    cout << size_classes[i] << ":\t" << all_size_class_counts[size_classes[i]] << endl;
  }
  cout << "----- END SIZE CLASS TABLE -----" << endl;

  cout << "Number of unique types found: " << all_type_set.size() << endl;

  if (is_field_file) {
    cout << "Field file name: " << field_file << endl;
    get_fields(field_file, all_type_set, db);
  }

  get_stats(type_map, all_stats_per_type, db);
  get_lines(type_map, all_buckets, buckets, db);

  cout << "Beginning to copy records to database..." << endl;

  sqlite3_stmt* stmt = 0;
  rc = sqlite3_prepare_v2(db, "INSERT INTO SUPERTABLE (FILE,LINE,TIMESTAMP,SIZE,ADDRESS,isNew,TYPE) " \
                              "VALUES (?, ?, ?, ?, ?, ?, ?);", -1, &stmt, 0);

  if (rc != SQLITE_OK) {
    fprintf(stderr, "Error after sqlite prepare: %s\n", sqlite3_errstr(rc));
    fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
    fclose(input_file);
    sqlite3_close(db);
    exit(-1);
  }

  rc = sqlite3_exec(db, "BEGIN TRANSACTION;", nullptr, nullptr, nullptr);

  if (rc != SQLITE_OK) {
    fprintf(stderr, "Error after begin transaction: %s\n", sqlite3_errstr(rc));
    fprintf(stderr, "DB error: %s\n", sqlite3_errmsg(db));
    fclose(input_file);
    sqlite3_close(db);
    exit(-1);
  }

  cout << "Number of pages: " << split_pages.size() << endl;

  for (auto& p: split_pages) {
    // printf("Here is the page address: %lu\n", p.first);
    if (p.second.sampled == CTD_NOT_SAMPLED) {
      bool take_for_type = false;
      for (auto& tp: p->second.included_types) {
        if (all_raw_type_count[tp] < num_pages_per_type) {
          p->second.sampled = CTD_SAMPLED_YES;
          take_for_type = true;
          break;
        }
      }
      if (take_for_type) {
        for (auto& tp: p->second.included_types)
          all_raw_type_count[tp]++;
      }
    }
    if (p->second.sampled == CTD_NOT_SAMPLED)
        p->second.sampled = (p->second.has_perf_addr || rand() < sample_portion*RAND_MAX) ? CTD_SAMPLED_YES : CTD_SAMPLED_NO;

    if (p.second.sampled == CTD_SAMPLED_YES) {
      // node_t* n = p.second.events.head;
      // unordered_map<uintptr_t, size_t> last_alloc_size{};
      // map<uintptr_t, uintptr_t> alloc_intervals{};  // all NON-OVERLAPPING intervals currently allocated
      for (const info_t* event : p.second.events) {
      // while (n != nullptr) {
      // info_t* event = n->data;
      //   size_t eventSize = event->typeofop ? event->size : last_alloc_size.find((uintptr_t) event->addr) != last_alloc_size.end() ? last_alloc_size.at((uintptr_t) event->addr) : 0;

      //   if (event->typeofop) {
      //     // printf("About to search for address %p\n", event->addr);
      //     map<uintptr_t, uintptr_t>::iterator i = alloc_intervals.lower_bound((uintptr_t) event->addr);
      //     if (i != alloc_intervals.end())
      //       i++;

      //     if (alloc_intervals.size() > 0) {
      //       do {
      //         if (i != alloc_intervals.begin())
      //           i--;
      //         if (i->first <= (uintptr_t) event->addr && i->second > (uintptr_t) event->addr + event->size ||   // event strictly contained inside i
      //             i->first < (uintptr_t) event->addr && i->second >= (uintptr_t) event->addr + event->size) {
      //           // remove i, DON'T add free for i
      //           alloc_intervals.erase(i->first);
      //           i = alloc_intervals.lower_bound((uintptr_t) event->addr);
      //           break;
      //         }
      //         else if (i->second <= (uintptr_t) event->addr) {   // event is after i
      //           break;
      //         }
      //         else if (i->first < (uintptr_t) event->addr + event->size) {   // event overlaps with i but is not contained within i
      //           // remove i, add free for i
      //           write_event_to_db(stmt, info_t(event->file, event->tindex_name, 0, event->timestamp-1, 0, (void*) i->first, false));
      //           alloc_intervals.erase(i->first);
      //           i = alloc_intervals.lower_bound((uintptr_t) event->addr);
      //         }
      //       } while (i != alloc_intervals.begin());
      //       // printf("FINISHED THE LOOP\n");
      //     }
      //     alloc_intervals.insert(pair<uintptr_t, uintptr_t>{(uintptr_t) event->addr, (uintptr_t) event->addr + event->size});         
      //     last_alloc_size.insert(pair<uintptr_t, size_t>{(uintptr_t) event->addr, event->size});
      //   }

      //   uint64_t page_num = (uint64_t) event->addr / page_size;
      //   uint64_t page_num_end = ((uint64_t) event->addr + eventSize - 1) / page_size; // Need to -1 for objects that end on page boundary

      //   if (page_num != page_num_end) {
      //     eventSize = page_size - ((uint64_t) event->addr % page_size);
      //     uint64_t new_event_addr = (uint64_t) event->addr + eventSize;
      //     int64_t rem_size = event->size - eventSize;
      //     do {
      //       uint64_t new_event_page_num = new_event_addr / page_size;
      //       if (boundary_crossers.find(new_event_page_num) == boundary_crossers.end())
      //         boundary_crossers.insert(pair<uint64_t, memory_page_t>{new_event_page_num, memory_page_t{}});
      //       boundary_crossers[new_event_page_num].add_event(new info_t{ event->file,
      //                                                                   event->tindex_name,
      //                                                                   event->line,
      //                                                                   event->timestamp,
      //                                                                   min((uint64_t)rem_size, page_num),
      //                                                                   (void*) new_event_addr,
      //                                                                   event->typeofop});
      //       new_event_addr += page_size;
      //       rem_size -= page_size;
      //     } while (rem_size > 0);
      //   }

        write_event_to_db(stmt, *event);
        
      // n = n->next;
      }
    }
  }

  // cout << "Number of boundary crossing pages: " << boundary_crossers.size() << endl;

  // for (auto& p: boundary_crossers) {
  //   if (all_pages.find(p.first) != all_pages.end()) {
  //     if (all_pages[p.first].sampled == CTD_SAMPLED_YES) {
  //       node_t* n = p.second.events.head;
  //       while (n != nullptr) {
  //         info_t* event = n->data;

  //         write_event_to_db(stmt, *event);

  //         n = n->next;
  //       }
  //     }
  //   }
  // }
  rc = sqlite3_exec(db, "END TRANSACTION;", nullptr, nullptr, nullptr);

  if (rc != SQLITE_OK) {
    cout << "SQL error: " << sqlite3_errstr(rc) << endl;
    // free(charmap);
    fclose(input_file);
    sqlite3_close(db);
    exit(-1);
  }

  fclose(input_file);
  sqlite3_close(db);
}
