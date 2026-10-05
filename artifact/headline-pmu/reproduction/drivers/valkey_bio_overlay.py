"""Author-only BIO terminal handshake draft. Not deployed/native-validated.

Invoke from the quiescent main thread after load ends. A sentinel per worker
uses the existing mutex queue; no cancellation or signal-handler logging.
"""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
from valkey_terminal_overlay import replace_once


def transform(source):
    if 'heaplensFinishBioProducers' in source:
        raise ValueError('BIO source already transformed')
    source = replace_once(source, '} bio_job;', '''} bio_job;
extern void memhook_terminal_flush(void);
extern void memhook_wait_report(uint64_t lo, uint64_t hi);
static uint64_t hl_bio_lo, hl_bio_hi;
static _Atomic(unsigned) hl_bio_finished;
static int hl_bio_requested;
static bio_job hl_bio_sentinels[sizeof bio_workers / sizeof *bio_workers];''')
    source = replace_once(source, '        int job_type = job->header.type;', '''        int job_type = job->header.type;
        if (job == &hl_bio_sentinels[bio_worker_num]) {
            memhook_terminal_flush();
            memhook_wait_report(hl_bio_lo, hl_bio_hi);
            atomic_fetch_add_explicit(&hl_bio_finished, 1, memory_order_release);
            continue; /* Static sentinel: neither free it nor decrement a job counter. */
        }''')
    return source + '''
int heaplensBioProducersReady(void) {
    if (hl_bio_requested) return 0;
    for (int type=0; type<BIO_NUM_OPS; ++type)
        if (atomic_load(&bio_jobs_counter[type])) return 0;
    return 1;
}
int heaplensFinishBioProducers(uint64_t lo, uint64_t hi) {
    serverAssert(inMainThread());
    if (lo > hi || !heaplensBioProducersReady()) return 0;
    hl_bio_lo=lo; hl_bio_hi=hi; hl_bio_requested=1;
    for (bio_worker_data *bwd=bio_workers; bwd!=bio_worker_end; ++bwd)
        mutexQueueAdd(bwd->bio_jobs, &hl_bio_sentinels[bioWorkerNum(bwd)]);
    monotime begin=getMonotonicUs();
    while (atomic_load_explicit(&hl_bio_finished, memory_order_acquire) !=
           sizeof bio_workers / sizeof *bio_workers) {
        if (getMonotonicUs()-begin > 60000000) _exit(99);
        usleep(1000);
    }
    return 1;
}
'''
