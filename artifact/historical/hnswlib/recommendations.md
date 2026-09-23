# Memory Layout A/B Test Recommendations

This sequence is based on `report.md`, especially the trace-backed finding that
the baseline level-0 row is 652 bytes for the recorded `M=16`, `dim=128` run:

- level-0 link count: 4 bytes
- level-0 neighbor IDs: 128 bytes
- vector payload: 512 bytes
- label: 8 bytes
- vector offset: 132 bytes
- row stride modulo 64: 12 bytes

The strongest measured problems are cache-line crossings and hot/cold cache-line
mixing in the level-0 row. Cache-set coverage was not the main issue. The test
plan should therefore isolate alignment, separation, and cold-data movement
rather than treating all layout changes as one large variant.

## Testing Principles

Use compile-time feature flags for each layout factor. Keep each factor
independently buildable so that it can be tested alone and in combination.

Recommended macro names:

| Factor | Macro | Purpose |
|---|---|---|
| A | `HNSWLIB_LAYOUT_LABEL_SOA` | Move labels out of the hot level-0 row. |
| B | `HNSWLIB_LAYOUT_VECTOR_SOA64` | Store vectors in a separate 64-byte-aligned slab. |
| C | `HNSWLIB_LAYOUT_L0_NEIGHBOR_SOA64` | Store level-0 neighbor IDs in a separate 64-byte-aligned slab. |
| D | `HNSWLIB_LAYOUT_UPPER_ALIGN64` | Align upper-layer neighbor arrays or blocks. |
| E | `HNSWLIB_LAYOUT_UPPER_NO_SENTINEL` | Remove the unused upper-link `+ 1` byte, or account for it consistently. |

Do not start with a padding-only level-0 row experiment as the main fix. For the
report workload, padding the current row enough to align both vector starts and
row stride would increase the `dim=128` row from 652 to roughly 768 bytes. For
`dim=16`, the row can grow from 204 to roughly 320 bytes. A separate vector slab
can align the 512-byte and 64-byte vector payloads with little or no per-vector
padding for these dimensions.

## Recommended Sequence

### 0. Establish a Reproducible Baseline

Run the baseline at the same scale and shape as the report before changing
layout. Record `qps_mean`, `us_per_query`, `build_seconds`, `build_rss_bytes`,
`query_rss_bytes`, `index_file_size`, and `recall_mean`.

Use explicit arguments rather than relying on script defaults:

```sh
python3 benchmark.py baseline \
  --dims 16,128 \
  --threads 1,24 \
  --elements 1000000 \
  --queries 100000 \
  --warmup 10000 \
  --iterations 5 \
  --m 16 \
  --ef-construction 200 \
  --ef 64 \
  --k 10 \
  --build-threads 24 \
  --query-mode indexed \
  --seed 47 \
  --numa-node 0 \
  --output results/baseline.csv
```

If `numactl` is unavailable on the target machine, omit `--numa-node 0`, but keep
that choice consistent for every variant.

### 1. Fix the Upper-Link Sentinel Accounting First

Implement `HNSWLIB_LAYOUT_UPPER_NO_SENTINEL` as a low-risk cleanup:

- Remove the unused `+ 1` byte in upper-link allocation and zeroing, or serialize
  and account for it consistently if it must remain.
- Verify `index_file_size()` matches serialized bytes.
- Verify fresh-built and loaded indexes have equivalent allocation shapes.

This is not expected to be the main speed win. It removes a layout/accounting
confounder before larger memory-layout experiments.

### 2. Move Labels Out of the Level-0 Row

Implement `HNSWLIB_LAYOUT_LABEL_SOA`:

- Allocate a separate `labeltype` array indexed by internal ID.
- Keep label access behind `getExternalLabeLp()`, `getExternalLabel()`, and
  `setExternalLabel()`.
- Update `saveIndex()`, `loadIndex()`, `resizeIndex()`, and Python pickle paths.

Why this belongs early:

- Labels are cold for bare-bone search and mostly needed when returning results.
- The report shows label mixing with vector and link data.
- It is conceptually simpler than splitting neighbor storage because label access
  already goes through narrow accessors.

Expected result:

- Lower hot/cold same-line mixing.
- Small index-layout size movement: roughly 8 MB for one million labels.
- Usually a smaller speed effect than vector or neighbor alignment, but useful as
  a clean independent factor.

### 3. Split Vectors Into a 64-Byte-Aligned Slab

Implement `HNSWLIB_LAYOUT_VECTOR_SOA64`:

- Allocate vector payloads in a separate 64-byte-aligned slab.
- Use `vector_stride = align_up(data_size_, 64)` only when needed.
- Preserve `getDataByInternalId()` as the only way search code obtains a vector
  pointer.
- Update serialization, loading, resizing, Python pickle/introspection, and any
  direct level-0 memory copy paths.

Why this is the highest-priority performance experiment:

- The report shows only 10 of 247 whole sampled vector payloads were 64-byte
  aligned in the final compact snapshot.
- Most 512-byte vectors occupy 9 cache lines instead of 8.
- For `dim=16`, a 64-byte vector often spans 2 cache lines instead of 1.
- A vector slab avoids the large memory growth of row-padding-only alignment.

Expected result:

- Strong reduction in vector `extra_crossings`.
- Reduced level-0 neighbor/vector same-line mixing.
- Potential query-speed improvement, especially in distance-heavy search.

### 4. Split Level-0 Neighbor IDs Into a 64-Byte-Aligned Slab

Implement `HNSWLIB_LAYOUT_L0_NEIGHBOR_SOA64`:

- Separate the level-0 count/deletion header from the neighbor ID array.
- Store level-0 neighbor IDs in a 64-byte-aligned slab with
  `neighbor_stride = align_up(maxM0_ * sizeof(tableint), 64)`.
- Add explicit accessors for count/status and neighbor pointer. Avoid relying on
  `(data + 1)` to find neighbor IDs in this variant.
- Preserve deletion-mark behavior and validate it with deletion tests.

Why this comes after the vector split:

- It is more invasive because current code assumes the count header and neighbor
  IDs are adjacent.
- It directly targets the second strongest trace-backed level-0 issue: 128-byte
  neighbor arrays commonly spanning 3 cache lines instead of 2.

Expected result:

- Strong reduction in level-0 neighbor `extra_crossings`.
- Further reduction in level-0 neighbor/vector same-line and adjacent-line mixes.
- Possible speedup in graph traversal, especially at larger `ef` and higher
  thread counts.

### 5. Test the Combined Level-0 Split Layout

After A, B, and C each work alone, test the cumulative level-0 layout:

```text
HNSWLIB_LAYOUT_LABEL_SOA=1
HNSWLIB_LAYOUT_VECTOR_SOA64=1
HNSWLIB_LAYOUT_L0_NEIGHBOR_SOA64=1
```

This is the most important cumulative A/B candidate. It should leave the hot
search data as:

- count/status storage
- aligned level-0 neighbor ID slab
- aligned vector slab
- separate label slab

Acceptance criteria:

- No recall regression.
- Save/load and pickle tests pass.
- HeapLENS shows vector and level-0 neighbor extra crossings largely eliminated.
- Query-speed gain is consistent across repeats, not only a best run.
- Memory growth is explainable and lower than the row-padding-only alternative.

### 6. Align Upper-Layer Neighbor Arrays

Implement `HNSWLIB_LAYOUT_UPPER_ALIGN64` after level-0 factors are understood:

- Either pad each upper-layer block so the neighbor array starts on a 64-byte
  boundary, or split upper count/status from upper neighbor IDs.
- Keep this as a separate factor because upper-layer blocks are sampled much less
  heavily than level-0 rows in the report.

Expected result:

- Eliminate the report's upper-neighbor finding: sampled 64-byte upper-neighbor
  arrays were all unaligned and crossed an extra cache line.
- Smaller total performance effect than level-0 vector and neighbor changes,
  but possibly useful at higher `M`, higher `ef`, or deeper graphs.

### 7. Audit Prefetches After Layout Changes

After splitting vectors or neighbors, re-check all prefetch sites that assume the
old packed layout. Keep prefetch target calculation behind accessors so every
layout variant uses the correct address.

Pay particular attention to prefetches of:

- next vector payload
- next level-0 neighbor slot
- upper-layer neighbor slots

Do this after the layout factors are implemented, not before; otherwise the audit
will be repeated for every storage shape.

## Factorial Test Matrix

For factor analysis, use A, B, and C as the primary level-0 factors:

| Variant | A: labels | B: vectors | C: level-0 neighbors |
|---|---:|---:|---:|
| `baseline` | 0 | 0 | 0 |
| `label_soa` | 1 | 0 | 0 |
| `vector_soa64` | 0 | 1 | 0 |
| `neighbor_soa64` | 0 | 0 | 1 |
| `label_vector` | 1 | 1 | 0 |
| `label_neighbor` | 1 | 0 | 1 |
| `vector_neighbor` | 0 | 1 | 1 |
| `full_l0_soa64` | 1 | 1 | 1 |

Then test D and E as secondary factors:

| Variant | Level-0 layout | D: upper align | E: no sentinel |
|---|---|---:|---:|
| `full_l0_soa64` | A+B+C | 0 | 0 |
| `full_l0_no_sentinel` | A+B+C | 0 | 1 |
| `full_l0_upper_align` | A+B+C | 1 | 0 |
| `full_layout` | A+B+C | 1 | 1 |

This keeps the first factor model focused on the trace-dominant level-0 effects,
then measures whether upper-layer cleanup adds anything once level-0 is fixed.

## Measurement Notes

Use the same seed, query mode, dimensions, `M`, `ef_construction`, `ef`, `k`,
thread counts, and NUMA policy for every variant. Randomize variant execution
order when running longer suites so thermal and system-load drift do not always
favor later variants.

At minimum, compare:

- `qps_mean`
- `us_per_query`
- `query_iteration_median_seconds`
- `build_seconds`
- `build_rss_bytes`
- `query_rss_bytes`
- `index_file_size`
- `recall_mean`

When available, add hardware counters:

- L1 data-cache load misses
- LLC load misses
- dTLB load misses
- cycles and instructions

Run HeapLENS again for the best single-factor variants and for
`full_l0_soa64`. The layout success criteria should be visible directly:

- vector payloads mostly 64-byte aligned
- level-0 neighbor arrays mostly 64-byte aligned
- vector and neighbor `extra_crossings` greatly reduced
- label/vector/link same-line mixes reduced or removed
- no new cache-set underutilization pattern

## Implementation Guardrails

Keep public behavior unchanged unless the benchmark variant explicitly opts into
a new serialized format. For every layout factor, update or verify:

- `saveIndex()` and `loadIndex()`
- `indexFileSize()`
- `resizeIndex()`
- `getDataByInternalId()`
- `getExternalLabeLp()` and label helpers
- level-0 and upper-link accessors
- Python `getAnnData()` and `setAnnData()`
- deletion and replacement paths
- save/load and pickle tests

Use `free()` for memory allocated by `malloc()` or aligned C allocation APIs. Do
not add new ownership paths that mix `malloc()` with `delete[]`.

Add small static assertions or comments around the packed 16-bit link count plus
deletion mark. That representation may remain, but the split-neighbor variant
should make count/status handling explicit instead of relying on ambiguous
4-byte header interpretation.
