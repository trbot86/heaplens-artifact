#include "myfirstallocator.h"

// #define new new (__FILE__,__LINE__,__FUNCTION__)

int main() {
    std::string* s = new std::string;
    std::vector<int> v(10);
    int* n = new int(6);
    dumpstatstofile("memstats");
    delete(s);
    delete(n);
    return 0;
}