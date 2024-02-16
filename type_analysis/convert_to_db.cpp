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
          cout << "PERF ACTUAL PAGE ADDRESS: " << cl_addr / cl_size << endl;
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
      cout << "SQL error creating table: " << zErrMsg << endl;
      sqlite3_free(zErrMsg);
      exit(-1);
    }
    else {
      cout << "Table created successfully" << endl;
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
    cout << "SQL error creating table: " << zErrMsg << endl;
    sqlite3_free(zErrMsg);
    exit(-1);
  }
  else {
    cout << "Table created successfully" << endl;
  }
}

int main(int argc, char* argv[]) {
  struct option long_opts[] = {
    {"perf-file",           required_argument,  0,  'p'},
    {"hitm-cutoff",         required_argument,  0,  'c'},
    {"sample-portion",      required_argument,  0,  's'},
    {"page-size",           required_argument,  0,  0},
    {"cacheline-size",      required_argument,  0,  0},
    {"num-pages-per-type",  required_argument,  0,  't'}
  };
  int opt_ind = 0;

  unordered_set<uint64_t> include_addrs{};
  unordered_set<uint64_t> skip_addrs{};
  int c;
  float sample_portion = -1.0;
  float cutoff = 5.0;
  const char* perf_file;
  int page_size = 4096;
  int cacheline_size = 64;
  int num_pages_per_type = 1;
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
        break;
      case 'c':
        cutoff = stof(optarg);
      case 's':
        sample_portion = stof(optarg);
        break;
      case 't':
        num_pages_per_type = stoi(optarg);
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

  if (perf_file)
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
      include_addrs.insert((uint64_t) event.addr / page_size);
      seen_types[typenamestr.str()] = seen_types[typenamestr.str()] + 1;
    }
  }

  cout << "Number of unique types found: " << seen_types.size() << endl;

  for (int i = 0, recs_taken = 0, num_file_writes = 0, bytes_copied = 0; i < num_structs; i++) {
    struct info_t event = *(filemap + i);
    uint64_t page_num = (uint64_t) event.addr / page_size;
    stringstream filenamestr, typenamestr;
    filenamestr << static_cast<const void*>(event.file);
    typenamestr << static_cast<const void*>(event.tindex_name);
    if (skip_addrs.find(page_num) == skip_addrs.end() &&
        (sample_portion < 0 ||
        include_addrs.find(page_num) != include_addrs.end() ||
        rand() < sample_portion*RAND_MAX)) {
      include_addrs.insert(page_num);
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
    else {
      skip_addrs.insert(page_num);
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
