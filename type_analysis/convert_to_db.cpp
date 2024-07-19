#include <iostream>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <sqlite3.h>
#include <fstream>
#include <map>
#include <sstream>
#include <cstring>
#include <sys/stat.h>
#include <vector>
#include <unordered_set>
#include <regex>
#include <getopt.h>
#include <string>

#define PADDING 64
#ifndef STRUCTS_PER_BLOCK
  #define STRUCTS_PER_BLOCK 1000000
#endif
#define MINIMUM_STRUCT_PER_BLOCK 1000000

using namespace std;

struct info_t {
    const char* file;
    const char* tindex_name;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;

    info_t() : file(nullptr), tindex_name(nullptr), line(0), timestamp(0), size(0), addr(nullptr) {}
};

struct perf_data {
  uint64_t addr;
  float hitm;
};

size_t bin_search(size_t* arr, size_t x, int begin, int end) {
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

map<string, string> construct_map(const char* filename) {
  map<string, string> retmap{};
  ifstream fd{filename};
  string val;
  for (string key; getline(fd, key, '|'); ) {
    getline(fd, val);
    retmap.insert(pair<string, string>{key, val});
  }
  return retmap;
}

void get_perf_addrs(const char* fname, float cutoff, int page_size, int cl_size, unordered_set<uint64_t> &addrs, sqlite3* db) {
  ifstream pfile;
  pfile.open(fname);
  string line;
  vector<struct perf_data> entries{};
  cmatch matches;
  regex rgx("[0-9]+\\s+(0x[a-f0-9]+)\\s+\\S+\\s+[0-9]+\\s+[0-9]+\\s+([0-9]+\\.[0-9]+)%");
  if (pfile.good()) {
    while(getline(pfile, line)) {
      if (regex_search(line.c_str(), matches, rgx)) {
        float hitm = stof(matches[2].str());
        if (hitm >= cutoff) {
          uint64_t cl_addr = strtoull(matches[1].str().c_str(), nullptr, 16);
          addrs.insert((cl_addr * cl_size) / page_size);
          // cout << "PERF ACTUAL PAGE ADDRESS: " << cl_addr / cl_size << endl;
          struct perf_data new_entry{cl_addr, hitm};
          entries.push_back(new_entry);
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
      cout << "SQL error creating perf table: " << zErrMsg << endl;
      sqlite3_free(zErrMsg);
      exit(-1);
    }
    else {
      cout << "Perf table created successfully" << endl;
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

    cout << "Done copying perf data to mem" << endl;
    sqlite3_exec(db, "BEGIN TRANSACTION;", nullptr, nullptr, nullptr);
    rc = sqlite3_exec(db, charmap, nullptr, 0, &zErrMsg);
    sqlite3_exec(db, "END TRANSACTION;", nullptr, nullptr, nullptr);

    if (rc != SQLITE_OK) {
      cout << "SQL error: " << zErrMsg << endl;
      sqlite3_free(zErrMsg);
      free(charmap);
      sqlite3_close(db);
      exit(-1);
    }

    cout << "Done writing perf table to file" << endl;

    free(charmap);
  }
  else {
    cout << "Failed to open perf output file " << fname << endl;
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
    cout << *seeniter << endl;

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

        // if (seen_types.find(type) != seen_types.end())
        //   cout << "Seen types contains type " << type << endl;
        // else
        //   cout << "NO" << type << " " << subtype << " " << name << " " << size << " " << offset << endl;

        if (seen_types.find(type_trim) != seen_types.end() &&
            (entries.find(type_trim) == entries.end() || entries[type_trim].find(name) == entries[type_trim].end())) {
          struct field_data new_entry{subtype, size, offset};
          entries[type_trim][name] = new_entry;
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
      cout << "SQL error creating fields table: " << zErrMsg << endl;
      sqlite3_free(zErrMsg);
      exit(-1);
    }
    else {
      cout << "Fields table created successfully" << endl;
    }

    cout << "Size of map: " << entries.size() << endl;
    map<string, map<string, struct field_data>>::iterator typeiter;
    char* charmap = (char *) calloc(entries.size(), 1000000);
    int bytes_copied = 0;
    int k = 0;
    for (typeiter = entries.begin(); typeiter != entries.end(); ) {
      string type = typeiter->first;
      if (k % 1000 == 0)
        cout << "WRITING ENTRY FOR " << type << endl;
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
        cout << "Copied fields data to mem" << endl;
        sqlite3_exec(db, "BEGIN TRANSACTION;", nullptr, nullptr, nullptr);
        rc = sqlite3_exec(db, charmap, nullptr, 0, &zErrMsg);
        sqlite3_exec(db, "END TRANSACTION;", nullptr, nullptr, nullptr);

        if (rc != SQLITE_OK) {
          cout << "SQL error: " << zErrMsg << endl;
          sqlite3_free(zErrMsg);
          free(charmap);
          sqlite3_close(db);
          exit(-1);
        }

        bytes_copied = 0;
        memset(charmap, 0, 1000000);
      }
    }

    cout << "Done writing fields table to file" << endl;

    free(charmap);
  }
  else {
    cout << "Failed to open fields output file " << fname << endl;
  }
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

int main(int argc, char* argv[]) {
  struct option long_opts[] = {
    {"perf-file",           required_argument,  0,  'p'},
    {"hitm-cutoff",         required_argument,  0,  'c'},
    {"sample-portion",      required_argument,  0,  's'},
    {"page-size",           required_argument,  0,  0},
    {"cacheline-size",      required_argument,  0,  0},
    {"num-pages-per-type",  required_argument,  0,  't'},
    {"field-dump",          required_argument,  0,  'f'},
    {"malloc-type-c",       required_argument,  0,  'm'}
  };
  int opt_ind = 0;

  unordered_set<uint64_t> include_addrs{};
  unordered_set<uint64_t> skip_addrs{};
  int c;
  float sample_portion = -1.0;
  float cutoff = 5.0;
  const char* perf_file;
  bool is_perf_file = false;
  const char* field_file;
  bool is_field_file = false;
  int page_size = 4096;
  int cacheline_size = 64;
  int num_pages_per_type = 1;
  const char* type_c_file;
  bool is_type_c = false;
  while ((c = getopt_long(argc, argv, "p:c:s:t:", long_opts, &opt_ind)) != -1) {
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
        cout << "NUM PAGES PER TYPE: " << num_pages_per_type << endl;
        break;
      case 'f':
        field_file = optarg;
        is_field_file = true;
        break;
      case 'm':
        type_c_file = optarg;
        is_type_c = true;
        break;
      default:
        break;
    }
  }

  sqlite3* db;
  int rc = sqlite3_open("allocs.sqlite", &db);
  char* zErrMsg = 0;

  if (rc) {
    cout << "Can't open database allocs.sqlite" << endl;
    exit(-1);
  }
  else {
    cout << "Opened database allocs.sqlite successfully" << endl;
  }

  if (is_perf_file)
    get_perf_addrs(perf_file, cutoff, page_size, cacheline_size, include_addrs, db);

  const char* input_filename = "binary_dump.txt";
  unsigned long int file_byte_size = 0;
  struct stat sb;

  FILE* input_file = fopen(input_filename, "r");
  if(input_file ==  NULL ){
		printf("%s not found \n", input_filename);
	}
	
	fstat(fileno(input_file), &sb);
  file_byte_size = (unsigned long int) sb.st_size;
  long int num_structs = file_byte_size / sizeof(struct info_t);

  map<string, string> type_map = construct_map("typeset_dump.txt");
  map<string, string> file_map = construct_map("fileset_dump.txt");
  map<string, int> seen_types{};
  unordered_set<string> type_set{};

  const int num_classes = 31;
  size_t size_classes [num_classes] = { 8, 16, 32, 48, 64, 80, 96, 128, 192, 224, 256, 320, 384, 512, 640, 768, 1024, 1280, 
                                        1536, 2048, 3584, 8192, 28672, 40960, 81920, 163840, 655360, 917504, 10485760, 20971520, 99999999999};
  map<size_t, int> size_class_counts{};
  for (int i = 0; i < num_classes; i++) {
    size_class_counts.insert(pair<size_t, int>{size_classes[i], 0});
  }

  create_supertable(db);

  printf("Number of structs in file: %ld\n", num_structs);

  struct info_t* filemap = (struct info_t*) mmap(NULL, file_byte_size, PROT_READ, MAP_PRIVATE, fileno(input_file), 0);

  if (filemap == MAP_FAILED) {
    cout << "Failed to map input file to memory" << endl;
  }
  else {
    cout << "Successfully mapped file" << endl;
  }

  char* charmap = (char *) malloc(800 * sizeof(char) * STRUCTS_PER_BLOCK);
  memset(charmap, 0, 800 * sizeof(char) * STRUCTS_PER_BLOCK);

  for (int i = 0; i < num_structs; i++) {
    struct info_t event = *(filemap + i);
    stringstream typenamestr;
    typenamestr << static_cast<const void*>(event.tindex_name);
    if (seen_types.find(typenamestr.str()) == seen_types.end()) {
      seen_types.insert(pair<string, int>{typenamestr.str(), 0});
    }
    if (seen_types.at(typenamestr.str()) < num_pages_per_type) {
      if (type_map.find(typenamestr.str()) != type_map.end()) {
        string type_trim = type_map.at(typenamestr.str());
        type_trim.erase(std::remove_if(type_trim.begin(), type_trim.end(), ::isspace), type_trim.end());
        type_set.insert(type_trim);
      }
      if (include_addrs.find((uint64_t) event.addr / page_size) == include_addrs.end()) {
        include_addrs.insert((uint64_t) event.addr / page_size);
        seen_types[typenamestr.str()] = seen_types[typenamestr.str()] + 1;
      }
    }
    if (event.size > 0) {
      int ind = bin_search(size_classes, event.size, 0, num_classes);
      // cout << "Size: " << event.size << " Index: " << ind << " Size class: " << size_classes[ind] << endl;
      size_class_counts[size_classes[ind]] = size_class_counts[size_classes[ind]] + 1;
    }
  }

  cout << "Size of the include_addrs: " << include_addrs.size() << endl;

  cout << "----- SIZE CLASS TABLE -----" << endl;
  for (int i = 0; i < num_classes; i++) {
    cout << size_classes[i] << ":\t" << size_class_counts[size_classes[i]] << endl;
  }
  cout << "----- END SIZE CLASS TABLE -----" << endl;

  cout << "Number of unique types found: " << seen_types.size() << endl;

  cout << "Field file name: " << field_file << endl;
  if (is_field_file)
    get_fields(field_file, type_set, db);

  for (int i = 0, recs_taken = 0, num_file_writes = 0, bytes_copied = 0; i < num_structs; i++) {
    struct info_t event = *(filemap + i);
    uint64_t page_num = (uint64_t) event.addr / page_size;
    uint64_t page_num_end = ((uint64_t) event.addr + event.size) / page_size;
    stringstream filenamestr, typenamestr;
    filenamestr << static_cast<const void*>(event.file);
    typenamestr << static_cast<const void*>(event.tindex_name);
    
    if (skip_addrs.find(page_num) == skip_addrs.end() &&
        include_addrs.find(page_num) == include_addrs.end()) {
        if (rand() < sample_portion*RAND_MAX) {
          include_addrs.insert(page_num);
        }
        else {
          skip_addrs.insert(page_num);
        }
    }

    if (skip_addrs.find(page_num_end) == skip_addrs.end() &&
        include_addrs.find(page_num_end) == include_addrs.end()) {
        if (rand() < sample_portion*RAND_MAX) {
          include_addrs.insert(page_num_end);
        }
        else {
          skip_addrs.insert(page_num_end);
        }
    }

    if (sample_portion < 0 || include_addrs.find(page_num) != include_addrs.end() || include_addrs.find(page_num_end) != include_addrs.end()) {
      bytes_copied += sprintf(charmap + bytes_copied, "INSERT INTO SUPERTABLE (FILE,LINE,TIMESTAMP,SIZE,ADDRESS,isNew,TYPE)" \
                                                      "VALUES ('%s', %d, %lu, %lu, %ld, %d, '%s');",
                                                event.file ?  file_map.at(filenamestr.str()).c_str() : "NULL",
                                                event.line,
                                                event.timestamp,
                                                event.size,
                                                (long) event.addr,
                                                event.typeofop,
                                                event.tindex_name ? type_map.at(typenamestr.str()).c_str() : "NULL");
      recs_taken++;
    }

    if (recs_taken == STRUCTS_PER_BLOCK || i == num_structs - 1) {
      cout << "Done mem copy" << endl;
      sqlite3_exec(db, "BEGIN TRANSACTION;", nullptr, nullptr, nullptr);
      rc = sqlite3_exec(db, charmap, nullptr, 0, &zErrMsg);
      sqlite3_exec(db, "END TRANSACTION;", nullptr, nullptr, nullptr);

      if (rc != SQLITE_OK) {
        cout << "SQL error: " << zErrMsg << endl;
        sqlite3_free(zErrMsg);
        free(charmap);
        fclose(input_file);
        sqlite3_close(db);
        exit(-1);
      }

      cout << "Done file write " << num_file_writes++ << endl;
      recs_taken = 0;
      bytes_copied = 0;
    }
  }

  cout << "Number of pages included in output: " << include_addrs.size() << endl;
  cout << "Number of pages excluded in output: " << skip_addrs.size() << endl;

  free(charmap);
  fclose(input_file);
  sqlite3_close(db);
}
