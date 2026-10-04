"""Cooperative terminal flush for the pinned Valkey trace build only.

Applied to a private instrumented source copy. No PMU/wait probes are included.
After client load ends, the controller retries DEBUG heaplens-finish until the
queues are quiescent; workers seal their own TLS before main seals its TLS.
The server must then exit. This is not a resumable checkpoint.
"""
from pathlib import Path


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Valkey terminal-flush source anchor mismatch: {old!r}')
    return text.replace(old, new, 1)


def transform_io(text):
    text = replace_once(text, 'static int io_threads_initialized = 0;', '''static int io_threads_initialized = 0;
extern void memhook_terminal_flush(void);
static _Atomic(unsigned) hl_finished_workers;
static int hl_terminal_requested;''')
    text = replace_once(text, '                switch (type) {', '''                switch (type) {
                case JOB_REQ_HEAPLENS_FINISH:
                    memhook_terminal_flush();
                    atomic_fetch_add_explicit(&hl_finished_workers, 1, memory_order_release);
                    break;''')
    return text + '''
int heaplensIOProducersReady(void) {
    if (hl_terminal_requested) return 0;
    if (server.io_threads_num == 1) return 1;
    if (!io_threads_initialized || server.active_io_threads_num != server.io_threads_num) return 0;
    size_t pending = getPendingIOThreadsJobs();
    int responses = getPendingIOResponsesCount();
    /* Publish staged free jobs, but never block on jobs requiring main-thread
     * response handling. Let the event loop handle those before retrying. */
    if (pending && !responses) {
        commitIOJobs();
        monotime begin = getMonotonicUs();
        while (getPendingIOThreadsJobs() && getMonotonicUs()-begin < 1000000) usleep(1000);
        pending = getPendingIOThreadsJobs();
        responses = getPendingIOResponsesCount();
    }
    return !pending && !responses;
}
void heaplensFinishIOProducers(void) {
    serverAssert(inMainThread());
    hl_terminal_requested = 1;
    for (int i = 1; i < server.io_threads_num; ++i) {
        spscEnqueue(&io_private_inbox[i], tagJob(NULL, JOB_REQ_HEAPLENS_FINISH), true);
        io_jobs_submitted++;
    }
    monotime begin = getMonotonicUs();
    while (atomic_load_explicit(&hl_finished_workers, memory_order_acquire) !=
           (unsigned)(server.io_threads_num - 1)) {
        if (getMonotonicUs()-begin > 60000000) _exit(99);
        usleep(1000);
    }
    if (server.io_threads_num > 1) drainIOThreadsQueue();
    memhook_terminal_flush();
}
'''


def transform_bio(text):
    text = replace_once(text, '} bio_job;', '''} bio_job;
extern void memhook_terminal_flush(void);
static _Atomic(unsigned) hl_bio_finished;
static int hl_bio_requested;
static bio_job hl_bio_sentinels[sizeof bio_workers / sizeof *bio_workers];''')
    text = replace_once(text, '        int job_type = job->header.type;', '''        int job_type = job->header.type;
        if (job == &hl_bio_sentinels[bio_worker_num]) {
            memhook_terminal_flush();
            atomic_fetch_add_explicit(&hl_bio_finished, 1, memory_order_release);
            continue; /* Static sentinel: no free and no normal job counter. */
        }''')
    return text + '''
int heaplensBioProducersReady(void) {
    if (hl_bio_requested) return 0;
    for (int type=0; type<BIO_NUM_OPS; ++type)
        if (atomic_load(&bio_jobs_counter[type])) return 0;
    return 1;
}
void heaplensFinishBioProducers(void) {
    serverAssert(inMainThread());
    hl_bio_requested=1;
    for (bio_worker_data *bwd=bio_workers; bwd!=bio_worker_end; ++bwd)
        mutexQueueAdd(bwd->bio_jobs, &hl_bio_sentinels[bioWorkerNum(bwd)]);
    monotime begin=getMonotonicUs();
    while (atomic_load_explicit(&hl_bio_finished, memory_order_acquire) !=
           sizeof bio_workers / sizeof *bio_workers) {
        if (getMonotonicUs()-begin > 60000000) _exit(99);
        usleep(1000);
    }
}
'''


def transform_debug(text):
    return replace_once(text, 'void debugCommand(client *c) {', '''
extern int heaplensIOProducersReady(void);
extern int heaplensBioProducersReady(void);
extern void heaplensFinishIOProducers(void);
extern void heaplensFinishBioProducers(void);
void debugCommand(client *c) {
    if (c->argc == 2 && !strcasecmp(objectGetVal(c->argv[1]), "heaplens-finish")) {
        if (!heaplensIOProducersReady() || !heaplensBioProducersReady()) {
            addReplyError(c,"HeapLENS producers not quiescent or already finalized"); return;
        }
        heaplensFinishBioProducers();
        heaplensFinishIOProducers();
        addReply(c,shared.ok);
        return;
    }
''')


def patch_source(root):
    root = Path(root) / 'src'
    if 'JOB_REQ_HEAPLENS_FINISH' in (root / 'io_threads.h').read_text():
        raise ValueError('Valkey terminal-flush patch already applied')
    transforms = {
        'io_threads.h': lambda s: replace_once(s, '    JOB_REQ_COUNT',
                                              '    JOB_REQ_HEAPLENS_FINISH,\n    JOB_REQ_COUNT'),
        'io_threads.c': transform_io, 'bio.c': transform_bio, 'debug.c': transform_debug,
    }
    # Validate every anchor before modifying any source.
    updates = {root / name: fn((root / name).read_text()) for name, fn in transforms.items()}
    for path, text in updates.items():
        path.write_text(text)
