// Author-only process-window probe, included once in the logger translation unit.
#ifndef HEAPLENS_VALKEY_WAIT_PROBE_H
#define HEAPLENS_VALKEY_WAIT_PROBE_H
#include "wait_events.h"
#include <time.h>
#include <sys/syscall.h>
#include <stdio.h>
#include <unistd.h>
#include <aio.h>
#include <errno.h>
// Bounded per-producer storage: overflow rejects the trial, never truncates it.
static thread_local hl_wait_events<4096> hl_valkey_waits;
static thread_local uint64_t hl_total_full_buffers = 0;
static uint64_t hl_valkey_now() {
    timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) _exit(90);
    return uint64_t(t.tv_sec)*1000000000ULL + t.tv_nsec;
}
static int hl_valkey_suspend(const aiocb *const *list, int count,
                             const timespec *timeout, unsigned kind) {
    uint64_t begin = hl_valkey_now();
    int result = aio_suspend(list, count, timeout), saved_errno = errno;
    uint64_t end = hl_valkey_now();
    if (!hl_valkey_waits.append(begin, end, kind, result != 0)) _exit(98);
    errno = saved_errno;
    return result;
}
// Call once per producer after terminal flush, with the same closed process
// window. Calling it does NOT establish that all producers have reported.
extern "C" void memhook_wait_report(uint64_t lo, uint64_t hi) {
    if (lo > hi) _exit(91);
    hl_window_wait_stats stats[2];
    if (!hl_valkey_waits.summarize(lo, hi, stats)) _exit(98);
    char producer[256];
    int length=snprintf(producer,sizeof(producer),
        "HL_PRODUCER {\"tid\":%ld,\"records\":%llu,\"record_bytes\":%llu}\n",
        syscall(SYS_gettid),
        (unsigned long long)(hl_total_full_buffers*MEMHOOK_MAX_BUFFER_SIZE+log_index),
        (unsigned long long)sizeof(memhook_info_t));
    if(length<0 || length>=int(sizeof(producer)) ||
       write(STDERR_FILENO,producer,length)!=length) _exit(92);
    for (unsigned kind=0; kind<2; ++kind) {
        const auto &s=stats[kind];
        char buf[768];
        int n=snprintf(buf,sizeof(buf),
            "HL_WINDOW_WAIT {\"tid\":%ld,\"kind\":%u,\"lo\":%llu,\"hi\":%llu,"
            "\"starts\":%llu,\"overlap_ns\":%llu,\"max_overlap_ns\":%llu,"
            "\"errors_starting\":%llu,\"crosses_begin\":%llu,\"crosses_end\":%llu,"
            "\"stored_events\":%llu}\n",
            syscall(SYS_gettid),kind,(unsigned long long)lo,(unsigned long long)hi,
            (unsigned long long)s.starts,(unsigned long long)s.overlap_ns,
            (unsigned long long)s.max_overlap_ns,(unsigned long long)s.errors_starting,
            (unsigned long long)s.crosses_begin,(unsigned long long)s.crosses_end,
            (unsigned long long)hl_valkey_waits.used);
        if(n<0 || n>=int(sizeof(buf)) || write(STDERR_FILENO,buf,n)!=n) _exit(92);
    }
}
#endif
