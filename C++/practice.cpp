#include <iostream>

void* new(size_t size, const char* file) {
    std::cout << file << std::endl;
    void* mem = std::malloc(size);
    return mem;
}

int main() {
#define new new(__FILE__)
return 0;
}