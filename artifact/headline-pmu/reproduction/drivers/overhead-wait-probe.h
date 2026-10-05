// Author-only diagnostic overlay. Included after the logger's TLS declarations.
#include <errno.h>
#include <time.h>
#include <sys/syscall.h>

struct hl_wait_stat { uint64_t count, ns, max_ns, errors; };
static thread_local hl_wait_stat hl_wait_stats[3][2] = {};
static thread_local uint64_t hl_full[3] = {};
static thread_local uint64_t hl_records[3] = {};
static thread_local uint64_t hl_phase_begin[3] = {};
static thread_local uint64_t hl_phase_end[3] = {};
static thread_local uint64_t hl_last_records = 0;
static thread_local int hl_phase = 0;

static uint64_t hl_now_ns() {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) _exit(90);
    return uint64_t(t.tv_sec) * 1000000000ULL + t.tv_nsec;
}
static uint64_t hl_record_total() {
    return (hl_full[0] + hl_full[1] + hl_full[2]) * MEMHOOK_MAX_BUFFER_SIZE + log_index;
}
extern "C" void memhook_wait_phase(int phase) {
    if (phase < 0 || phase > 2) _exit(91);
    uint64_t n=hl_record_total(), t=hl_now_ns();
    hl_records[hl_phase] += n - hl_last_records;
    hl_last_records=n; hl_phase_end[hl_phase]=t;
    hl_phase=phase; hl_phase_begin[phase]=t;
}
static int hl_wait(const struct aiocb *const list[], int n,
                   const struct timespec *timeout, int kind) {
    int phase=hl_phase;
    uint64_t begin=hl_now_ns();
    int rc=aio_suspend(list,n,timeout), saved_errno=errno;
    uint64_t elapsed=hl_now_ns()-begin;
    auto &s=hl_wait_stats[phase][kind];
    ++s.count; s.ns+=elapsed;
    if(elapsed>s.max_ns) s.max_ns=elapsed;
    if(rc!=0) ++s.errors;
    errno=saved_errno;
    return rc;
}
static void hl_report() {
    uint64_t now=hl_now_ns(), n=hl_record_total();
    hl_records[hl_phase]+=n-hl_last_records;
    hl_phase_end[hl_phase]=now;
    long tid=syscall(SYS_gettid);
    for(int p=0;p<3;++p) {
        char buf[1024];
        auto &a=hl_wait_stats[p][0]; auto &b=hl_wait_stats[p][1];
        int size=snprintf(buf,sizeof(buf),
            "HL_WAIT {\"tid\":%ld,\"phase\":%d,\"records\":%llu,\"full_buffers\":%llu,"
            "\"begin_ns\":%llu,\"end_ns\":%llu,"
            "\"reuse_count\":%llu,\"reuse_ns\":%llu,\"reuse_max_ns\":%llu,\"reuse_errors\":%llu,"
            "\"shutdown_count\":%llu,\"shutdown_ns\":%llu,\"shutdown_max_ns\":%llu,\"shutdown_errors\":%llu}\n",
            tid,p,(unsigned long long)hl_records[p],(unsigned long long)hl_full[p],
            (unsigned long long)hl_phase_begin[p],(unsigned long long)hl_phase_end[p],
            (unsigned long long)a.count,(unsigned long long)a.ns,(unsigned long long)a.max_ns,(unsigned long long)a.errors,
            (unsigned long long)b.count,(unsigned long long)b.ns,(unsigned long long)b.max_ns,(unsigned long long)b.errors);
        if(size<0 || size>=int(sizeof(buf)) || write(STDERR_FILENO,buf,size)!=size) _exit(92);
    }
}
