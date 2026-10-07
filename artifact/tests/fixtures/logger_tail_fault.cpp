#define _GNU_SOURCE
#include <dlfcn.h>
#include <unistd.h>
#include <cerrno>
#include <cstdlib>
extern int global_fd;
extern "C" ssize_t write(int fd, const void* buffer, size_t bytes) {
    typedef ssize_t (*Writer)(int,const void*,size_t);
    static Writer real_write=reinterpret_cast<Writer>(dlsym(RTLD_NEXT,"write"));
    static int calls=0;
    if(fd==global_fd && fd>2) {
        int mode=std::atoi(std::getenv("HEAPLENS_TEST_TAIL_FAULT"));
        ++calls;
        if((mode==1 || mode==3) && calls==1) {errno=EINTR;return -1;}
        if((mode==2 || mode==3) && bytes>7) bytes=7;
        if(mode==4) return 0;
        if(mode==5) {errno=ENOSPC;return -1;}
    }
    return real_write(fd,buffer,bytes);
}
