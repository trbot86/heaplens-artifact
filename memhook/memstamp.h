#ifndef __MEMSTAMP_H
#define __MEMSTAMP_H

using namespace std;

struct info_t {
    char *file;
    type_index tindex;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;
    //char padding[PADDING];

    info_t() : file(nullptr), tindex(typeid(void)), line(0), timestamp(0), size(0), addr(nullptr) {}
};

class MemStamp
{
    public:
    //Why did we do this?
        // char const * const filename;
        char *filename;
        int const lineNum;
    public:
        MemStamp(char const *filename, int lineNum);
        ~MemStamp();
};

MemStamp::MemStamp(char const *filename, int lineNum)
    : filename(nullptr), lineNum(lineNum) { }
MemStamp::~MemStamp() { }

class MemStampCollector {
  private:
//   slot* sarr;
//   info_t* allArrays;

//   int get_slot(thread::id id);

public:
    MemStampCollector();

    ~MemStampCollector();

    void copy(info_t &unit_log);
    // void update(const char * file, unsigned int line, type_index* tindex);
    // void threadexit();
};

#endif      //__MEMSTAMP_H