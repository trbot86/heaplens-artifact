#include <iostream>
#include <thread>
#include <cstdlib>
#include <unistd.h>
#include <experimental/source_location>

// void* operator new (std::size_t size) __attribute__((always_inline));
void atexit_handler();

void atexit_handler() {
    std::cout << "exit_handler_called " << std::endl;
}

struct info_t {
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
};

void thread_call_handler() {
    std::cout << std::this_thread::get_id() << " :thread" << std::endl;
    for(int i = 0;i < 2;i++) {
        sleep(1);
    }
}

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
const int result = std::atexit(atexit_handler);
std::thread t1(thread_call_handler);
int* n = new int(5);
int* t = new int(5);
int* rt = new int(5);
#ifdef CHECKING
    std::cout <<  "abc\n";
#endif
// t1.detach();
t1.join();
// fclose(fp);
return 0;
}