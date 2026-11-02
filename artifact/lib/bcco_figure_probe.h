#ifndef FIG9_PROBE_H
#define FIG9_PROBE_H
// Diagnostic-only, process-local mapping audit. Linux v6.8 PAGEMAP_SCAN ABI.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <dlfcn.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <x86intrin.h>
struct hl_region { uint64_t start, end, categories; };
struct hl_scan_arg {
    uint64_t size, flags, start, end, walk_end, vec, vec_len, max_pages;
    uint64_t category_inverted, category_mask, category_anyof_mask, return_mask;
};
static constexpr uint64_t HL_PRESENT=8, HL_HUGE=64, HL_BIG=2097152;
#define HL_SCAN _IOWR('f', 16, struct hl_scan_arg)
static void hl_die(const char* msg) { perror(msg); exit(81); }
static int hl_scan(int fd, uint64_t begin, uint64_t end, FILE* out, uint64_t* present, uint64_t* huge) {
    hl_region regions[1024];
    *present=*huge=0;
    while(begin<end) {
        hl_scan_arg a={}; a.size=sizeof(a); a.start=begin; a.end=end;
        a.vec=(uint64_t)regions; a.vec_len=1024; a.category_mask=HL_PRESENT;
        a.return_mask=HL_PRESENT|HL_HUGE;
        int n=ioctl(fd,HL_SCAN,&a);
        if(n<0) return -1;
        for(int i=0;i<n;++i) {
            *present+=regions[i].end-regions[i].start;
            if(regions[i].categories&HL_HUGE) *huge+=regions[i].end-regions[i].start;
            if(out) fprintf(out,"%llx %llx %llu\n",(unsigned long long)regions[i].start,
                (unsigned long long)regions[i].end,(unsigned long long)regions[i].categories);
        }
        if(a.walk_end<=begin) { errno=EIO; return -1; }
        begin=a.walk_end;
    }
    return 0;
}
static void hl_copy_proc(const char* stage,const char* suffix,const char* name) {
    char from[256],to[512],buf[16384];
    snprintf(from,sizeof(from),"/proc/self/%s",name);
    snprintf(to,sizeof(to),"%s/%s-%s-%s",getenv("HL_FIG9_EVIDENCE"),stage,suffix,name);
    int in=open(from,O_RDONLY),out=open(to,O_WRONLY|O_CREAT|O_EXCL,0644);
    if(in<0||out<0) hl_die("snapshot open");
    ssize_t n; while((n=read(in,buf,sizeof(buf)))>0) {
        ssize_t offset=0; while(offset<n) { ssize_t w=write(out,buf+offset,n-offset); if(w<=0)hl_die("snapshot write");offset+=w; }
    }
    if(n<0) hl_die("snapshot read"); close(in);close(out);
}
static void hl_mapping_snapshot(const char* stage,const char* suffix,bool collapse) {
    char path[512],line[4096];
    hl_copy_proc(stage,suffix,"maps");hl_copy_proc(stage,suffix,"smaps");
    hl_copy_proc(stage,suffix,"smaps_rollup");hl_copy_proc(stage,suffix,"numa_maps");
    snprintf(path,sizeof(path),"%s/%s-%s-pagemap.txt",getenv("HL_FIG9_EVIDENCE"),stage,suffix);
    FILE* out=fopen(path,"wx"); FILE* maps=fopen("/proc/self/maps","r");
    int fd=open("/proc/self/pagemap",O_RDONLY);
    if(!out||!maps||fd<0) hl_die("mapping snapshot open");
    FILE* advice=nullptr;
    if(collapse) {
        snprintf(path,sizeof(path),"%s/%s-collapse.txt",getenv("HL_FIG9_EVIDENCE"),stage);
        advice=fopen(path,"wx"); if(!advice)hl_die("collapse output");
    }
    while(fgets(line,sizeof(line),maps)) {
        unsigned long long start,end,offset,inode; char perms[8],dev[32],name[2048]="";
        if(sscanf(line,"%llx-%llx %7s %llx %31s %llu %2047[^\n]",&start,&end,perms,&offset,dev,&inode,name)<6)hl_die("maps parse");
        // Restrict to private, readable/writable anonymous mappings (including heap/stack).
        if(perms[0]!='r'||perms[1]!='w'||perms[3]!='p'||inode!=0)continue;
        uint64_t present,huge;
        if(hl_scan(fd,start,end,out,&present,&huge)<0)hl_die("PAGEMAP_SCAN");
        if(collapse && present) {
            for(uint64_t p=(start+HL_BIG-1)&~(HL_BIG-1);p+HL_BIG<=end;p+=HL_BIG) {
                uint64_t pp,hh;
                if(hl_scan(fd,p,p+HL_BIG,nullptr,&pp,&hh)<0)hl_die("collapse pre-scan");
                if(!pp || hh==HL_BIG)continue;
                errno=0; int advice_rc=madvise((void*)p,HL_BIG,MADV_HUGEPAGE); int ae=errno;
                errno=0; int rc=madvise((void*)p,HL_BIG,25 /* MADV_COLLAPSE */); int e=errno;
                fprintf(advice,"%llx %llu %llu %d %d %d %d\n",(unsigned long long)p,
                    (unsigned long long)pp,(unsigned long long)hh,advice_rc,ae,rc,e);
            }
        }
    }
    if(advice)fclose(advice);fclose(out);fclose(maps);close(fd);
}
static void hl_fig9_snapshot(const char* stage) {
    bool collapse=strcmp(getenv("HL_FIG9_THP"),"on")==0;
    fprintf(stderr,"HL_FIG9_SNAPSHOT_BEGIN %s %llu\n",stage,(unsigned long long)__rdtsc());
    hl_mapping_snapshot(stage,"before",collapse);
    hl_mapping_snapshot(stage,"after",false);
    fprintf(stderr,"HL_FIG9_SNAPSHOT_END %s %llu\n",stage,(unsigned long long)__rdtsc());
}
typedef int (*hl_ctl)(const char*,void*,size_t*,void*,size_t);
static void hl_fig9_identity(bool separate) {
    const char* paths[]={getenv("HL_FIG9_GLOBAL"),getenv("HL_FIG9_NODE")};
    void* mallocs[2]={};
    for(int i=0;i<(separate?2:1);++i) {
        void* h=dlopen(paths[i],RTLD_NOW); if(!h){fprintf(stderr,"%s\n",dlerror());exit(82);}
        hl_ctl ctl=(hl_ctl)dlsym(h,"mallctl");mallocs[i]=dlsym(h,"malloc");
        const char *version=nullptr,*thp=nullptr;size_t n=sizeof(version);
        if(!ctl||!mallocs[i]||ctl("version",&version,&n,nullptr,0))exit(83);
        n=sizeof(thp);if(ctl("opt.thp",&thp,&n,nullptr,0))exit(84);
        const char* expected=strcmp(getenv("HL_FIG9_THP"),"on")==0?"always":"never";
        if(strncmp(version,"5.3.0",5)||strcmp(thp,expected))exit(85);
        fprintf(stderr,"HL_ALLOCATOR %d path=%s malloc=%p mallctl=%p version=%s thp=%s\n",i,paths[i],mallocs[i],(void*)ctl,version,thp);
    }
    if(separate && mallocs[0]==mallocs[1])exit(86);
}
#endif
