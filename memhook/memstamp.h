#ifndef __MEMSTAMP_H
#define __MEMSTAMP_H

using namespace std;

struct memhook_info_t {
    const char* file;
    const char* tindex_name;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;

    memhook_info_t() : file(nullptr), tindex_name(nullptr), line(0), timestamp(0), size(0), addr(nullptr) {
        (void) 0;
    }
};

class MemStamp
{
    public:
    //check if this should be char const * or const char *
        char const *filename;
        int const lineNum;
    public:
        MemStamp(char const *filename, int lineNum);
        ~MemStamp();
};

class MemStampCollector {
  private:

  public:
    MemStampCollector();

    ~MemStampCollector();

    void copy(memhook_info_t &unit_log);
    // void update(const char * file, unsigned int line, type_index* tindex);
    // void threadexit();
};

#endif      //__MEMSTAMP_H