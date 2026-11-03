#include "bcco_figure_probe.h"
int main() {
    hl_fig9_identity(true);
    auto global=(hl_ctl)dlsym(dlopen(getenv("HL_FIG9_GLOBAL"),RTLD_NOW),"mallctl");
    auto node=(hl_ctl)dlsym(dlopen(getenv("HL_FIG9_NODE"),RTLD_NOW),"mallctl");
    unsigned before,after,created;size_t n=sizeof(before);
    if(global("arenas.narenas",&before,&n,nullptr,0))return 2;
    n=sizeof(created);if(node("arenas.create",&created,&n,nullptr,0))return 3;
    n=sizeof(after);if(global("arenas.narenas",&after,&n,nullptr,0))return 4;
    unsigned node_after;n=sizeof(node_after);if(node("arenas.narenas",&node_after,&n,nullptr,0))return 5;
    if(before!=after || node_after<=created || node_after==after)return 6;
    printf("INDEPENDENT_ALLOCATORS global_before=%u global_after=%u node_after=%u created=%u\n",before,after,node_after,created);
    void* raw=mmap(nullptr,3*HL_BIG,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if(raw==MAP_FAILED)return 7;
    uint64_t p=((uint64_t)raw+HL_BIG-1)&~(HL_BIG-1);
    if(madvise((void*)p,HL_BIG,MADV_NOHUGEPAGE))return 8;
    memset((void*)p,1,HL_BIG);
    int fd=open("/proc/self/pagemap",O_RDONLY);uint64_t present,huge;
    if(hl_scan(fd,p,p+HL_BIG,nullptr,&present,&huge)||present!=HL_BIG||huge)return 9;
    if(madvise((void*)p,HL_BIG,MADV_HUGEPAGE)||madvise((void*)p,HL_BIG,25))return 10;
    if(hl_scan(fd,p,p+HL_BIG,nullptr,&present,&huge)||present!=HL_BIG||huge!=HL_BIG)return 11;
    printf("PAGEMAP_SCAN_VERIFIED small_then_huge=%llu\n",(unsigned long long)huge);
    close(fd);munmap(raw,3*HL_BIG);return 0;
}
