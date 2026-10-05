"""Diagnostics only, after measurement; keep the rejecting predicates unchanged."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
from valkey_terminal_overlay import replace_once


def io_diagnostics(source):
    return replace_once(source, '''    return !hl_terminal_requested && io_threads_initialized &&
        server.active_io_threads_num == server.io_threads_num &&
        !getPendingIOThreadsJobs() && !getPendingIOResponsesCount();''', '''    size_t pending = getPendingIOThreadsJobs();
    int responses = getPendingIOResponsesCount();
    int ready = !hl_terminal_requested && io_threads_initialized &&
        server.active_io_threads_num == server.io_threads_num && !pending && !responses;
    if (!ready) fprintf(stderr,
        "HL_IO_NOT_READY requested=%d initialized=%d active=%d configured=%d jobs=%zu responses=%d reads=%lld writes=%lld\\n",
        hl_terminal_requested,io_threads_initialized,server.active_io_threads_num,
        server.io_threads_num,pending,responses,(long long)server.stat_io_reads_pending,
        (long long)server.stat_io_writes_pending);
    return ready;''')


def bio_diagnostics(source):
    return replace_once(source, '''    if (hl_bio_requested) return 0;
    for (int type=0; type<BIO_NUM_OPS; ++type)
        if (atomic_load(&bio_jobs_counter[type])) return 0;''', '''    if (hl_bio_requested) {
        fprintf(stderr,"HL_BIO_NOT_READY already_requested=1\\n"); return 0;
    }
    for (int type=0; type<BIO_NUM_OPS; ++type) {
        unsigned long long pending=atomic_load(&bio_jobs_counter[type]);
        if (pending) {
            fprintf(stderr,"HL_BIO_NOT_READY type=%d jobs=%llu\\n",type,pending); return 0;
        }
    }''')
