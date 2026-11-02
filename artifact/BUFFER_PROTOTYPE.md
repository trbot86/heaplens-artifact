# Optional bounded logging buffers

This branch contains an experimental buffer policy, separate from the logger
correctness candidate. It has not established an application speedup and is not
the artifact's released default.

Two buffers remain the default. With a larger `MEMHOOK_MAX_BUFFERS`, the logger
first reuses a completed buffer. If all allocated buffers are still in flight,
it may allocate another, subject to both the per-thread limit and a shared
process-wide budget for extra buffers. Budget exhaustion or an unsuccessful
optional allocation falls back to waiting. AIO control blocks never move while
requests are pending; every completion is validated and reaped exactly once.

After draining at thread exit, unused buffers are freed. A nonempty tail stays
owned by the existing final-output pool; any extra-buffer reservation associated
with it stays charged until process exit. This conservative accounting can
limit later growth under thread churn, but cannot exceed the extra-buffer cap.
The cap covers extra data buffers, not the original two buffers per active
producer, retained original tails, application memory, or small control arrays.

For example, build the optional policy with:

```bash
cd memhook
make clean
make USE_TEMPLATE=1 MEMHOOK_MAX_BUFFERS=4 \
  MEMHOOK_EXTRA_BUFFER_BUDGET_BYTES=536870912
```

`MEMHOOK_MAX_BUFFER_SIZE` also accepts an explicit build-time override; the
default remains one million 40-byte records. Each full-size buffer is about
38.15 MiB. The original two buffers across 24 active producers represent about
1.79 GiB of reserved data capacity. Unconditionally using four doubles that to
3.58 GiB. The example shared cap instead permits at most thirteen extra
full-size buffers (about 496 MiB) across all producers. Actual resident pages
and buffer high-water marks must be measured separately.

Correctness validation includes 36 deterministic pressure cases covering zero
records, exact and partial buffers, up to eight allowed buffers, restrictive
global caps, nine successive/concurrent producers and failed optional growth.
The mock checks that submitted bytes remain unchanged until completion and
that every record appears exactly once. Thirty real-AIO fault cases exercise
interrupted waits, short writes and failed submission/completion/wait calls.
The actual shared library also passes the 82-object multithreaded native
fixture with two and four allowed buffers and tiny buffers that turn over
frequently. All results are functional checks, not throughput measurements.

More buffering can absorb bursts; it cannot by itself remove a sustained
storage-bandwidth deficit. The delayed-I/O fixture deliberately demonstrates
that fewer operation-loop waits can be accompanied by more final-drain waits.
Any efficacy study must report operation completion, total drained completion,
record equality, peak RSS and buffer high-water marks. Compare policies with
identical trace coverage before considering an updated overhead claim.

The prototype also chooses any completed slot before waiting, even when its
maximum is two. A pilot should therefore keep three controls: the corrected
default two-buffer implementation, this prototype capped at two, and the
prototype capped at four with a 512 MiB shared extra-buffer budget. This
separates the effect of choosing a completed slot from adding storage capacity.
The prototype now includes the same allocation and retirement repairs as the
correctness candidate; actual-library checks pass under both two/four limits.
