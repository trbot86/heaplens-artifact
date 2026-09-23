# Memory Layout Recommendations For Progressive A/B Testing

Source report:
`heaplens_runs/jemalloc_docker_20260608/v2_export/heaplens_analysis.txt`

Source DB:
`heaplens_runs/jemalloc_docker_20260608/allocs.sqlite`

## Key Observations

- `robj` dominates the sampled layout: 102,453 sampled allocation rows, about 4.0 MB sampled bytes, and 47.4% of <=64-byte `robj` rows cross a 64-byte cache line.
- The dominant allocation site is `object.c:75`, which accounts for 102,356 sampled `robj` rows. Most are 40-byte objects.
- The aggregate report attributes 2,833 extra cache-line crossings to `robj`, far above every other type.
- `raxNode` is the next meaningful small-object target. It has 1,590 sampled rows and 94 <=64-byte cache-line crossings, with allocation/reallocation concentrated in `rax.c:178`, `rax.c:256`, `rax.c:398`, `rax.c:699`, `rax.c:704`, and `rax.c:1003`.
- The report shows repeated same-line and adjacent-line mixes between `raxNode` and `void` allocations. The main `void` site is SDS growth at `sds.c:280`.
- `listNode` and `struct list` have visible crossing rates, but their volume is much lower than `robj`.
- Large client/event buffers contribute page footprint, especially `networking.c:297`, `ae.c:83`, `ae.c:84`, and `queues.c`, but they are low-count relative to object churn.

## Measurement Discipline

Use the current run as `A0`:

```text
run_dir=heaplens_runs/jemalloc_docker_20260608
ops_per_sec=1080142.06
p99_latency_ms=3.407
p999_latency_ms=3.743
used_memory=219952120
used_memory_rss=306642944
mem_fragmentation_ratio=1.39
supertable_rows=106338
distinct_types=47
field_rows=3086
```

For each variant, run at least 3 repetitions before accepting an effect. Prefer 5 if variance is high. Keep the same workload, jemalloc backend, NUMA placement, sampling, and exporter settings.

Track these response metrics:

- Throughput: `ops_per_sec`.
- Tail latency: `p99_latency_ms`, `p999_latency_ms`.
- Memory: `used_memory`, `used_memory_rss`, `mem_fragmentation_ratio`.
- Layout: cache-line crossing counts, same-line mixes, adjacent-line mixes, page fragments, selected page clusters.

Useful SQLite checks after each run:

```sql
SELECT TYPE, COUNT(*) rows,
       SUM(CASE WHEN SIZE <= 64 AND ((ADDRESS % 64) + SIZE) > 64 THEN 1 ELSE 0 END) crosses,
       ROUND(100.0 * SUM(CASE WHEN SIZE <= 64 AND ((ADDRESS % 64) + SIZE) > 64 THEN 1 ELSE 0 END) / COUNT(*), 1) pct_cross
FROM SUPERTABLE
WHERE isNew = 1
GROUP BY TYPE
HAVING rows >= 20
ORDER BY crosses DESC;

SELECT FILE, LINE, TYPE, COUNT(*) rows,
       SUM(CASE WHEN SIZE <= 64 AND ((ADDRESS % 64) + SIZE) > 64 THEN 1 ELSE 0 END) crosses
FROM SUPERTABLE
WHERE isNew = 1 AND SIZE <= 64
GROUP BY FILE, LINE, TYPE
HAVING crosses > 0
ORDER BY crosses DESC;
```

## Recommended Sequence

### A0: Reproduce Baseline

Run the current benchmark 3 more times before changing layout. This establishes variance for jemalloc, NUMA scheduling, and memtier timing.

Acceptance gate: baseline coefficient of variation is small enough that a 2-3% throughput or p99 effect is distinguishable. If not, increase repetitions before testing layout changes.

### B1: Isolate `robj` With A Line-Aware Allocator

Target:

- `valkey/src/object.c:75`
- optionally `valkey/src/object.c:179`

Change:

- Route common `robj` allocations through a dedicated wrapper.
- First variant: 64-byte align only the common `object.c:75` path.
- Do not change object fields yet.

Reason:

- The current 40-byte common `robj` placement crosses cache lines about half the time.
- A line-aware allocator should reduce `robj` crossing count sharply, but it may increase RSS because 40-byte objects become effectively 64-byte placements.

Primary hypothesis:

- Tail latency improves if `robj` header/key access is on one cache line.

Risk:

- RSS and fragmentation can rise substantially. This is a diagnostic branch, not necessarily the final design.

### B2: Compact Or Split The Common `robj` Layout

Target:

- `valkey/src/server.h:816`
- `valkey/src/object.c:57`
- `valkey/src/object.c:75`

Change candidates:

- Disable embedded-key storage for the common SET-string object path so the `robj` header returns to a smaller fixed allocation.
- Alternatively split cold metadata such as embedded key/expire storage away from the hot `robj` header.
- Keep the hot `robj` header and frequently touched fields within 32 bytes if feasible.

Reason:

- A 32-byte common object can be placed two per 64-byte line without crossings.
- This may beat B1 because it reduces crossings without the 64-byte-per-object RSS penalty.

Primary hypothesis:

- `robj` crossing count drops while RSS stays closer to baseline than B1.

Risk:

- More pointer chasing if keys or expire metadata are moved out of line.
- Extra key allocations may reduce memory wins unless reuse is good.

### B3: Compare `robj` Strategies Directly

Run a controlled comparison:

- `A0`: current jemalloc.
- `B1`: 64-byte aligned `robj`.
- `B2`: compact/split `robj`.
- `B1+B2`: compact/split plus line-aware placement, if B2 still leaves crossings.

Decision:

- Keep the strategy with the best throughput/tail-latency improvement per RSS cost.
- If B1 improves latency but has unacceptable RSS, retain it only as an upper-bound diagnostic.

### C1: Segregate `raxNode` From SDS/Generic `void` Allocations

Targets:

- `valkey/src/rax.c`
- `valkey/src/rax.h`
- allocator wrappers behind `rax_malloc`, `rax_realloc`, and `rax_free`
- SDS growth sites at `valkey/src/sds.c:280` and `valkey/src/sds.c:293`

Change:

- Put `raxNode` allocations in a distinct small-object arena or pool.
- Keep SDS/generic `void` buffers out of that arena.

Reason:

- The report repeatedly shows `raxNode`/`void` same-line and adjacent-line mixing.
- Separating these allocation streams is a low semantic-risk way to test whether those mixes matter.

Primary hypothesis:

- Same-line and adjacent-line mixes between `raxNode` and `void` fall without large object-size changes.

Risk:

- Arena segregation can increase fragmentation. Track RSS and jemalloc fragmentation.

### C2: Add Size-Class-Aware `raxNode` Growth

Targets:

- `valkey/src/rax.c:178`
- `valkey/src/rax.c:256`
- `valkey/src/rax.c:398`
- `valkey/src/rax.c:699`
- `valkey/src/rax.c:704`
- `valkey/src/rax.c:1003`

Change:

- Test modest reserve capacity for small non-compressed nodes so repeated `rax_realloc` calls do not move nodes through many tiny sizes.
- Keep a separate variant that only pads small `raxNode` allocations to stable size classes, such as 16, 32, or 64 bytes.

Reason:

- `raxNode` is variable-sized and reallocated often. Exact sizing is memory efficient, but it increases relocation and mixes node sizes densely with unrelated objects.

Primary hypothesis:

- Fewer `raxNode` reallocations and fewer line crossings improve lookup/update locality.

Risk:

- Padding or reserve capacity may waste memory in trees with many sparse nodes.

### D1: Pool `listNode` And `struct list` Together

Targets:

- `valkey/src/adlist.c:47`
- `valkey/src/adlist.c:128`

Change:

- Test a list-owned pool that allocates `struct list` and its initial `listNode` objects from the same region.
- Alternative: 32-byte-align `listNode` allocations only.

Reason:

- `listNode` has a 22.4% crossing rate and `struct list` has a 48.9% crossing rate, but the volume is small.
- This is a second-order change and should follow `robj`/`raxNode`.

Primary hypothesis:

- Small improvement in list traversal locality and lower list-related crossings.

Risk:

- Low workload relevance for this benchmark; do not overfit unless later reports show list growth.

### E1: Align Large Per-Client/Event Buffers By Page Or Huge-Page Policy

Targets:

- `valkey/src/networking.c:297`
- `valkey/src/ae.c:83`
- `valkey/src/ae.c:84`
- `valkey/src/queues.c`

Change:

- Page-align large persistent buffers.
- Optionally allocate large per-thread/event buffers from a separate arena.

Reason:

- These are low-count but high-byte allocations. They influence page layout and RSS more than small-object cache-line behavior.

Primary hypothesis:

- Page clustering becomes cleaner and TLB/page-level behavior improves.

Risk:

- Little effect on this object-heavy workload. Keep this after small-object experiments.

## Factor Analysis Plan

After the single-factor A/B runs, keep only factors that show a measurable effect or explain a report pattern. Suggested factors:

```text
R = robj treatment
    0: baseline
    1: 64-byte line-aware placement
    2: compact/split common robj

X = rax/SDS segregation
    0: baseline allocation stream
    1: separate raxNode arena/pool

G = rax growth policy
    0: exact sizing
    1: reserve/pad small raxNode growth

L = list pooling
    0: baseline
    1: listNode/struct-list pool or 32-byte listNode alignment

P = large-buffer placement
    0: baseline
    1: page/arena placement for large persistent buffers
```

Recommended progression:

1. Run one-factor tests: `R1`, `R2`, `X1`, `G1`, `L1`, `P1`.
2. Select the best `R` level. Do not carry both `R1` and `R2` unless both are close and affect different metrics.
3. Run a fractional factorial over the selected `R`, `X`, and `G` first. These are the factors most connected to report evidence.
4. Add `L` and `P` only if the first factorial leaves meaningful unexplained variance or if later reports show list/page pressure.
5. Confirm the best combined design with at least 5 repetitions and a fresh HeapLENS export.

## Priority Order

1. `robj` crossing reduction.
2. `robj` compact/split design versus line-aware placement.
3. `raxNode`/SDS allocation segregation.
4. `raxNode` growth and size-class policy.
5. `listNode` and list structure pooling.
6. Large buffer page/arena placement.

Avoid starting with global jemalloc tuning. It can change every allocation stream at once and will make factor attribution difficult. Use targeted wrappers first, then consider allocator-wide policy only after the important factors are known.
