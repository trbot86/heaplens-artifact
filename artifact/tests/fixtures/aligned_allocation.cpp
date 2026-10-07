#include "memhook_interface.h"
#include <cstdio>
#include <cstdlib>
#include <cerrno>

int main() {
    void *cptr=nullptr, *cppptr=nullptr;
    int cresult=posix_memalign_s(&cptr,64,64,104,1,4);
    int cppresult=posix_memalign<char,105,1>(&cppptr,64,64);
    std::printf("target c %p\ntarget cpp %p\n",cptr,cppptr);
    std::printf("slot c %p\nslot cpp %p\n",static_cast<void*>(&cptr),static_cast<void*>(&cppptr));
    if(cresult || cppresult || !cptr || !cppptr) return 1;
    // POSIX leaves the output unchanged on error; neither wrapper may log it.
    void *failed_c=reinterpret_cast<void*>(0x12345678);
    void *failed_cpp=reinterpret_cast<void*>(0x87654321);
    int ec=posix_memalign_s(&failed_c,3,64,106,1,4);
    int epp=posix_memalign<char,107,1>(&failed_cpp,3,64);
    std::printf("error_slot c %p\nerror_slot cpp %p\n",static_cast<void*>(&failed_c),static_cast<void*>(&failed_cpp));
    if(ec!=EINVAL || epp!=EINVAL) return 2;
    if(failed_c!=reinterpret_cast<void*>(0x12345678) || failed_cpp!=reinterpret_cast<void*>(0x87654321)) return 3;
    std::free(cptr);std::free(cppptr);
    return 0;
}
