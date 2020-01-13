#include "myfirstallocator.h"

#define NewWithDebug new (__FILE__,__LINE__,__FUNCTION__)

int main() {
    trackalloc<int> talloc;
    std::string* s = new std::string;
    std::vector<int, trackalloc<int>> v(10, talloc);
    return 0;
}