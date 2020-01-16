#include <iostream>
#include <unistd.h>
#include <experimental/source_location>

void* operator new (std::size_t size) __attribute__((always_inline));

struct info_t {
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
};

void* operator new (std::size_t size) {
    std::experimental::source_location loc = std::experimental::source_location::current();
    std::cout << loc.line() << std::endl;
    return std::malloc(size);
}

int main() {
// FILE* fp = fopen("./memstats", "r");
// info_t info;

// while(!feof(fp)) {
//     fread(&info,sizeof(info_t),1,fp);
//     std::cout << info.line << " " << info.timestamp << 
//     " " << info.size << " " << info.addr << std::endl;
// }
int* n = new int(5);
int* t = new int(5);
int* rt = new int(5);
#ifdef CHECKING
    std::cout <<  "abc\n";
#endif
// fclose(fp);
return 0;
}