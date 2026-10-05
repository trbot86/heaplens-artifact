#pragma once
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <unistd.h>
#include <sys/syscall.h>
#include <stdexcept>
extern "C" void memhook_wait_phase(int) __attribute__((weak));
struct hl_hnsw_call { unsigned phase, iteration; uint64_t call; };
static std::atomic<unsigned> hl_hnsw_phase{0}, hl_hnsw_iteration{0};
static std::atomic<uint64_t> hl_hnsw_calls{0};
static void hl_hnsw_set_phase(unsigned phase, unsigned iteration) {
    if (phase>2 || iteration>5) throw std::runtime_error("invalid HNSW phase");
    hl_hnsw_iteration.store(iteration); hl_hnsw_phase.store(phase);
}
static hl_hnsw_call hl_hnsw_context() {
    return {hl_hnsw_phase.load(),hl_hnsw_iteration.load(),++hl_hnsw_calls};
}
struct hl_hnsw_worker {
    hl_hnsw_call context; size_t worker;
    hl_hnsw_worker(hl_hnsw_call c, size_t w):context(c),worker(w) {
        if(memhook_wait_phase) memhook_wait_phase(c.phase);
        emit("begin");
    }
    ~hl_hnsw_worker() {
        emit("end");
        if(memhook_wait_phase) memhook_wait_phase(2);
    }
    void emit(const char* boundary) {
        char buffer[256];
        int n=snprintf(buffer,sizeof(buffer),
            "HL_HNSW_WORKER {\"tid\":%ld,\"call\":%llu,\"iteration\":%u,\"phase\":%u,\"worker\":%zu,\"boundary\":\"%s\"}\n",
            syscall(SYS_gettid),(unsigned long long)context.call,context.iteration,context.phase,worker,boundary);
        if(n<0 || n>=int(sizeof(buffer)) || write(STDERR_FILENO,buffer,n)!=n) _exit(92);
    }
};
