"""Author-only cooperative I/O-worker terminal handshake (not deployed).

The caller must close measurement first, stop client load, and invoke from the
main thread with no pending jobs/responses. This covers I/O workers plus main;
it does not establish completeness for other Valkey background producers.
"""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
from valkey_terminal_overlay import replace_once


def transform_header(header):
    if 'JOB_REQ_HEAPLENS_FINISH' in header:
        raise ValueError('worker header already transformed')
    return replace_once(header, '    JOB_REQ_COUNT',
                        '    JOB_REQ_HEAPLENS_FINISH,\n    JOB_REQ_COUNT')


def transform_source(source):
    if 'heaplensFinishIOProducers' in source:
        raise ValueError('worker source already transformed')
    source = replace_once(source, 'static int io_threads_initialized = 0;', '''static int io_threads_initialized = 0;
extern void memhook_terminal_flush(void);
extern void memhook_wait_report(uint64_t lo, uint64_t hi);
static uint64_t hl_window_lo, hl_window_hi;
static _Atomic(unsigned) hl_finished_workers;
static int hl_terminal_requested;
''')
    source = replace_once(source, '                switch (type) {', '''                switch (type) {
                case JOB_REQ_HEAPLENS_FINISH:
                    memhook_terminal_flush();
                    memhook_wait_report(hl_window_lo, hl_window_hi);
                    atomic_fetch_add_explicit(&hl_finished_workers, 1, memory_order_release);
                    break;''')
    # This function refuses a non-quiescent call, rather than draining queues
    # while main is unable to service responses (which could deadlock).
    return source + '''
/* Author-only: invoke once after measurement, from main, then exit normally.
 * Return 0 means not ready and has no terminal side effects. */
int heaplensIOProducersReady(void) {
    return !hl_terminal_requested && io_threads_initialized &&
        server.active_io_threads_num == server.io_threads_num &&
        !getPendingIOThreadsJobs() && !getPendingIOResponsesCount();
}
int heaplensFinishIOProducers(uint64_t lo, uint64_t hi) {
    serverAssert(inMainThread());
    if (lo > hi || !heaplensIOProducersReady()) return 0;
    hl_window_lo = lo; hl_window_hi = hi;
    hl_terminal_requested = 1;
    for (int i = 1; i < server.io_threads_num; ++i) {
        spscEnqueue(&io_private_inbox[i], tagJob(NULL, JOB_REQ_HEAPLENS_FINISH), true);
        io_jobs_submitted++;
    }
    /* The external controller must additionally enforce a wall-time bound. */
    monotime begin = getMonotonicUs();
    while (atomic_load_explicit(&hl_finished_workers, memory_order_acquire) !=
           (unsigned)(server.io_threads_num - 1)) {
        if (getMonotonicUs() - begin > 60000000) _exit(99);
        usleep(1000);
    }
    drainIOThreadsQueue();
    memhook_terminal_flush();
    memhook_wait_report(lo, hi);
    return 1;
}
'''
