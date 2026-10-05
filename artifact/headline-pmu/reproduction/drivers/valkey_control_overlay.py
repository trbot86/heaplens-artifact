"""Author-only DEBUG command to finalize logging after a closed PMU window.

Not deployed. Input timestamps must be CLOCK_MONOTONIC nanoseconds from the
same host and must match the recorded PMU gate, not merely client wall time.
"""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
from valkey_terminal_overlay import replace_once


def transform(source):
    if 'heaplens-finish' in source:
        raise ValueError('control source already transformed')
    return replace_once(source, 'void debugCommand(client *c) {', '''
extern int heaplensIOProducersReady(void);
extern int heaplensBioProducersReady(void);
extern int heaplensFinishIOProducers(uint64_t lo, uint64_t hi);
extern int heaplensFinishBioProducers(uint64_t lo, uint64_t hi);
void debugCommand(client *c) {
    if (c->argc == 4 && !strcasecmp(objectGetVal(c->argv[1]), "heaplens-finish")) {
        long long lo, hi;
        if (getLongLongFromObjectOrReply(c,c->argv[2],&lo,NULL)!=C_OK ||
            getLongLongFromObjectOrReply(c,c->argv[3],&hi,NULL)!=C_OK) return;
        if (lo < 0 || hi < lo) {
            addReplyError(c,"invalid HeapLENS measurement window"); return;
        }
        if (!heaplensIOProducersReady() || !heaplensBioProducersReady()) {
            addReplyError(c,"HeapLENS producers not quiescent or already finalized"); return;
        }
        /* Main is sealed last, after both sets of worker terminal jobs. */
        if (!heaplensFinishBioProducers((uint64_t)lo,(uint64_t)hi) ||
            !heaplensFinishIOProducers((uint64_t)lo,(uint64_t)hi)) _exit(99);
        addReply(c,shared.ok);
        return;
    }
''')
