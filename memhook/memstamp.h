#ifndef __MEMSTAMP_H
#define __MEMSTAMP_H

#include <cstdint>

using namespace std;

struct memhook_info_t {
    size_t line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    uint16_t file;
    uint16_t tindex_name;
    bool typeofop;

    memhook_info_t() : file(0), tindex_name(0), line(0), timestamp(0), size(0), addr(nullptr) {
        (void) 0;
    }
};

class MemStamp
{
public:
    uint16_t filename;
    int const lineNum;

    MemStamp(uint16_t fn, int ln) : filename(fn), lineNum(ln) {}
};

class MemStampCollector {
private:

public:
    MemStampCollector();

    ~MemStampCollector();

    void copy(memhook_info_t &unit_log);
};

#endif      //__MEMSTAMP_H