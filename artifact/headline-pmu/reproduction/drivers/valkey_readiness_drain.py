"""Post-window bounded publication/drain of queued jobs with no pending responses."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
from valkey_terminal_overlay import replace_once


def transform(source):
    return replace_once(source, '''    size_t pending = getPendingIOThreadsJobs();
    int responses = getPendingIOResponsesCount();''', '''    size_t pending = getPendingIOThreadsJobs();
    int responses = getPendingIOResponsesCount();
    /* Main may have staged a fire-and-forget free job while processing the
     * control command. Publish it before waiting; no response processing or
     * recursive command execution is allowed here. Never drain with pending
     * responses, since a worker could otherwise block on a full outbox. */
    if (!hl_terminal_requested && io_threads_initialized &&
        server.active_io_threads_num == server.io_threads_num && pending && !responses) {
        commitIOJobs();
        monotime begin = getMonotonicUs();
        while (getPendingIOThreadsJobs() && getMonotonicUs()-begin < 1000000)
            usleep(1000);
        pending = getPendingIOThreadsJobs();
        responses = getPendingIOResponsesCount();
    }''')
