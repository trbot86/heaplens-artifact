# Memory Layout Problems and Anomalies

Entrypoint reviewed: `benchmark.py`

Scope: local repository tree only. I read `heaplens.pdf` from this tree, inspected the root source, inspected the instrumented copied worktree under `heaplens_runs/docker_24t_full_default_20260609_nasus/work/...`, and analyzed:

- `heaplens_runs/docker_24t_full_default_20260609_nasus/v2_export/heaplens_analysis.txt`
- `heaplens_runs/docker_24t_full_default_20260609_nasus/v2_export/heaplens_pages_v2.txt`
- `heaplens_runs/docker_24t_full_default_20260609_nasus/v2_export/compact/heaplens_*`

## Summary

Problems were found. The strongest trace-backed issue is the baseline level-0 HNSW row layout: link metadata, neighbor IDs, vector payload, and label are packed into a 652-byte row for the recorded 128-dimensional run. That row size is not a multiple of 64 bytes, and the vector payload begins 132 bytes into the row. The result is widespread cache-line crossing and cache-line mixing for the two hottest per-element regions: neighbor IDs and vector payloads.

The HeapLENS trace confirms this is not only a theoretical code-layout concern:

- In final compact snapshot 8, only 10 of 247 whole level-0 vector payloads were 64-byte aligned.
- Only 11 of 273 whole level-0 neighbor arrays were 64-byte aligned.
- All 23 whole upper-neighbor arrays in the final compact snapshot were unaligned and crossed an extra cache line.
- Aggregate same-line mixes repeatedly show level-0 neighbor arrays sharing cache lines with vector payloads, and labels mixing with next-row link/vector data.

I did not find strong evidence of cache-set underutilization for the sampled level-0 element/vector/neighbor regions: by the final snapshot they cover all 64 L1 sets. The main HeapLENS findings are cache-line crossing, hot/cold line mixing, page-boundary fragments, and upper-link layout/accounting anomalies.

## HeapLENS Paper: Relevant Diagnostics

The HeapLENS paper frames memory layout issues around:

- memory leaks and unexpected allocation-count growth,
- heap or page fragmentation,
- cache-line crossings and field scattering,
- false sharing and adjacent-line effects,
- cache-set underutilization,
- type-aware and field-aware page/cache-line visualization over time.

The report data in this repository exposes those categories as:

- `extra_crossings`: objects or pseudo-fields that cross more cache lines than required by their size.
- `same_line_mixes`: distinct types/pseudo-fields occupying the same cache line.
- `adjacent_mixes`: distinct types/pseudo-fields appearing within the configured adjacent-line window, 128 bytes here.
- `page_fragments`: objects split across sampled 4 KiB pages.
- `l1_start_sets` and `l1_cover_sets`: cache-set occupancy by object start address and by covered cache lines.
- `field_crossings`: field-level crossing data for recorded C++ object fields.

The compact files add per-object details: offset in page, cache line, L1 set, alignment bucket, visible fragment size, actual allocation/object size, split kind, container flag, and type.

## Trace Context

The recorded HeapLENS run is `docker_24t_full_default_20260609_nasus`.

Benchmark configuration from `benchmark.log`:

- `layout_variant=0`, `layout_name=baseline`
- `elements=1000000`
- `dim=128`
- `queries=100000`
- `iterations=5`
- `threads=24`, `build_threads=24`
- `M=16`, `ef_construction=200`, `ef_search=64`, `k=10`
- input data bytes: 512,000,000

HeapLENS sampling/export context:

- page size: 4096 bytes
- cache line size: 64 bytes
- adjacent-line window: 128 bytes
- L1 sets: 64
- selected pages: 54
- clustered pages: 15127
- clusters: 34

The trace was captured from the copied instrumented worktree under `heaplens_runs/.../work/...`. For layout variant 0, its level-0 layout matches the root baseline formula in `hnswlib/hnswalg.h`: level-0 links, vector bytes, and label are packed with no alignment padding.

## Type Alias Expansion

The HeapLENS files use aliases. I use these readable short names below:

| Alias | Readable name | Full type |
|---|---|---|
| A | HNSW index object | `hnswlib::HierarchicalNSW<float>` |
| B | visited-list object | `hnswlib::VisitedList` |
| C | visited-list pool | `hnswlib::VisitedListPool` |
| D | benchmark input data slab | `hnswlib::heaplens::HeapLensBenchmarkInputData` |
| E | benchmark query IDs | `hnswlib::heaplens::HeapLensBenchmarkQueryIds` |
| F | HNSW label | `hnswlib::heaplens::HeapLensHnswLabel` |
| G | level-0 element row | `hnswlib::heaplens::HeapLensHnswLevel0Element` |
| H | level-0 link count | `hnswlib::heaplens::HeapLensHnswLevel0LinkCount` |
| I | level-0 neighbor ID array | `hnswlib::heaplens::HeapLensHnswLevel0Neighbors` |
| J | level-0 slab | `hnswlib::heaplens::HeapLensHnswLevel0Slab` |
| K | upper-link count | `hnswlib::heaplens::HeapLensHnswUpperLinkCount` |
| L | upper-links block | `hnswlib::heaplens::HeapLensHnswUpperLinksBlock` |
| M | upper-link pointer table | `hnswlib::heaplens::HeapLensHnswUpperLinksPointerTable` |
| N | upper-neighbor ID array | `hnswlib::heaplens::HeapLensHnswUpperNeighbors` |
| O | upper-link padding byte | `hnswlib::heaplens::HeapLensHnswUpperPadding` |
| P | vector payload | `hnswlib::heaplens::HeapLensHnswVectorPayload` |
| Q | visited-list mark array | `hnswlib::heaplens::HeapLensHnswVisitedList` |

Aliases for benchmark query IDs and visited-list mark arrays are present in the type table, but no compact sampled objects of those types appear in `heaplens_analysis.txt`.

## Cache-Line Crossing and Alignment Problems

### Level-0 rows make hot regions unaligned

Root source:

- `hnswlib/hnswalg.h:120` computes the level-0 link region as `maxM0_ * sizeof(tableint) + sizeof(linklistsizeint)`.
- `hnswlib/hnswalg.h:121` computes the level-0 row as links + vector + label.
- `hnswlib/hnswalg.h:122` places the vector immediately after the link region.
- `hnswlib/hnswalg.h:123` places the label immediately after the vector.
- `hnswlib/hnswalg.h:126` allocates all level-0 rows in one contiguous `malloc` slab.

For the recorded trace (`M=16`, `dim=128`):

- link count: 4 bytes
- level-0 neighbor ID array: `2 * M * 4 = 128` bytes
- vector payload: `128 * sizeof(float) = 512` bytes
- label: 8 bytes
- level-0 row size: `4 + 128 + 512 + 8 = 652` bytes
- vector payload offset: 132 bytes
- label offset: 644 bytes
- row stride modulo 64: `652 % 64 = 12`

This creates a repeating misalignment pattern. The vector payload and level-0 neighbor ID array start at row-start + 4 modulo 64. Only one start position in the 16-row cycle gives a 64-byte aligned vector or neighbor array.

HeapLENS compact snapshot 8 confirms this:

| Region | Whole objects in compact snapshot 8 | 64-byte aligned whole objects |
|---|---:|---:|
| vector payload | 247 | 10 |
| level-0 neighbor ID array | 273 | 11 |
| level-0 link count | 279 | 18 |
| level-0 element row | 234 | 13 |

HeapLENS `extra_crossings` in snapshot 8:

| Region | Extra crossings / sampled rows |
|---|---:|
| level-0 neighbor ID array | 262 / 290 |
| vector payload | 237 / 315 |
| level-0 element row | 29 / 324 |
| HNSW label | 23 / 280 |

The vector distance kernels use unaligned SIMD loads (`_mm512_loadu_ps`, `_mm256_loadu_ps`, `_mm_loadu_ps`) in `hnswlib/space_l2.h:39`, `hnswlib/space_l2.h:74`, and `hnswlib/space_l2.h:112`, so this is not a correctness bug on x86. It is a layout/performance anomaly: most 512-byte vectors occupy 9 cache lines instead of 8, and most 128-byte neighbor arrays occupy 3 cache lines instead of 2.

For the root `benchmark.py` default dimensions, `dim=16` is also affected: the vector payload is exactly 64 bytes but starts at offset 132, so it commonly spans two cache lines instead of one.

### Upper-link neighbor arrays also cross extra cache lines

Upper layers use a 4-byte count followed by `M` 4-byte neighbor IDs. With `M=16`, the upper-neighbor ID array is exactly 64 bytes, but it starts after the count, so it is normally offset by 4 bytes rather than aligned.

HeapLENS compact snapshot 8:

| Region | Whole objects in compact snapshot 8 | 64-byte aligned whole objects | Extra crossings / sampled rows |
|---|---:|---:|---:|
| upper-neighbor ID array | 23 | 0 | 23 / 25 |
| upper-links block | 12 | 3 | not listed |

The instrumented worktree has an explicit `aligned-upper-links` variant, which is a good sign that this issue was identified as a layout experiment target.

## Cache-Line Mixing and Field-Scattering-Like Layout

HeapLENS reports `field_crossings: none`, so the sampled C++ object fields for `HierarchicalNSW`, `VisitedList`, and `VisitedListPool` were not the issue. The problem is in manually packed regions inside slabs.

Aggregate `same_line_mixes` from `heaplens_analysis.txt`, with aliases expanded:

| Same cache-line mix | Aggregate count |
|---|---:|
| level-0 neighbor ID array + vector payload | 1290 |
| HNSW label + level-0 link count + level-0 neighbor ID array + vector payload | 975 |
| HNSW label + level-0 link count + level-0 neighbor ID array | 202 |
| HNSW label + vector payload | 184 |
| level-0 link count + level-0 neighbor ID array | 76 |
| upper-link count + upper-neighbor ID array | 76 |
| upper-neighbor ID array + upper-link padding byte | 68 |

Aggregate `adjacent_mixes` show the same pattern within the 128-byte adjacent-line window:

| Adjacent-line mix | Aggregate count |
|---|---:|
| level-0 neighbor ID array + vector payload | 1335 |
| HNSW label + level-0 link count + level-0 neighbor ID array + vector payload | 1158 |
| HNSW label + level-0 link count + level-0 neighbor ID array | 98 |
| HNSW label + vector payload | 96 |
| upper-neighbor ID array + upper-link padding byte | 46 |

This is a hot/cold and cross-purpose packing issue:

- The HNSW search path frequently reads level-0 neighbor IDs and vector payloads.
- The label is cold for the bare-bone search path and is mainly needed when results are returned.
- Because rows are packed, labels at the end of one element can share or sit adjacent to link metadata and vector data of the next element.
- Level-0 neighbor IDs and vector payloads share cache lines because the vector starts immediately after a 132-byte link region instead of at a cache-line boundary.

This matches the HeapLENS paper's cache-line crossing and field-scattering class of problems, even though these "fields" are manually logged subregions rather than C++ struct fields.

## Page and TLB Locality Anomalies

The baseline level-0 slab is one large contiguous allocation. In the recorded run, its actual size is 652,000,000 bytes (`1,000,000 * 652`), and compact rows show the level-0 slab as page-sized middle fragments. That is expected for a huge slab and is not itself heap fragmentation.

The anomaly is that individual rows and vector payloads frequently straddle 4 KiB page boundaries because the row stride is 652 bytes rather than a page/cache-line friendly value.

Final snapshot 8 `page_fragments`:

| Region | Page fragments |
|---|---:|
| level-0 element row | 90 |
| vector payload | 68 |
| level-0 slab | 45 |
| level-0 neighbor ID array | 17 |
| upper-neighbor ID array | 2 |
| HNSW label | 2 |

Aggregate `page_fragments`:

| Region | Page fragments |
|---|---:|
| level-0 element row | 428 |
| level-0 slab | 360 |
| vector payload | 326 |
| level-0 neighbor ID array | 75 |
| benchmark input data slab | 27 |
| upper-link pointer table | 24 |

Given HNSW's random graph traversal, page splits can contribute to TLB pressure and reduce prefetch effectiveness. HeapLENS does not show malloc-style fragmentation here; it shows page-boundary splits caused by dense packed row geometry.

## Cache-Set Occupancy

HeapLENS does not show a strong level-0 cache-set underutilization problem in the final sampled snapshot:

| Region | L1 start sets in snapshot 8 | L1 cover sets in snapshot 8 |
|---|---:|---:|
| vector payload | 63 / 64 | 64 / 64 |
| level-0 neighbor ID array | 63 / 64 | 64 / 64 |
| level-0 element row | 63 / 64 | 64 / 64 |
| HNSW label | 63 / 64 | 64 / 64 |

The huge slabs themselves start at L1 set 0 because page-aligned fragments begin at page offset 0, but their contents cover all sets. I would not classify the main level-0 layout as a cache-set underutilization issue based on this trace.

Upper-link regions have sparse set coverage in the sampled data:

- upper-neighbor ID array: 23 start sets, 38 cover sets in snapshot 8
- upper-links block: 11 start sets, 23 cover sets in snapshot 8
- upper-link padding byte: 21 start sets, 21 cover sets in snapshot 8

This is based on only 12 sampled upper-link blocks in snapshot 8, so it is weaker evidence than the level-0 findings. The upper-link alignment problem is still clear from the cache-line crossing data.

## Upper-Link Padding and Accounting Mismatch

The root source allocates one extra byte for every upper-link block:

- `hnswlib/hnswalg.h:1207` allocates `size_links_per_element_ * curlevel + 1`.
- `hnswlib/hnswalg.h:1210` zeroes that same `+ 1` size.

The HeapLENS instrumentation logs this extra byte as `upper-link padding byte`:

- `heaplens_runs/.../hnswlib/hnswalg.h:1536` computes `upper_links_size = size_links_per_element_ * curlevel + 1`.
- `heaplens_runs/.../hnswlib/hnswalg.h:1553` logs the final byte as `HeapLensHnswUpperPadding`.

Compact snapshot 8 shows:

- 10 upper-link blocks of 69 bytes.
- 2 upper-link blocks of 137 bytes.
- 22 one-byte upper-link padding objects.

This byte is not included in the root `indexFileSize()` or serialized output:

- `hnswlib/hnswalg.h:677` to `hnswlib/hnswalg.h:680` count only `size_links_per_element_ * element_levels_[i]`.
- `hnswlib/hnswalg.h:706` to `hnswlib/hnswalg.h:710` serialize only the counted size.

Impact:

- Freshly built and loaded indexes do not have identical upper-link allocation shapes.
- `index_file_size()` under-reports in-memory upper-link allocation by one byte per element with at least one upper level.
- The extra byte also creates visible `upper-neighbor ID array + upper-link padding byte` same-line and adjacent-line mixes in HeapLENS.

The byte appears unused, so this is a low-severity memory-accounting/layout inconsistency rather than a correctness issue.

## Packed Link Metadata Hazard

`linklistsizeint` is defined as an unsigned int, but list counts are accessed through `unsigned short int`:

- `hnswlib/hnswalg.h:940` reads only the low 16 bits.
- `hnswlib/hnswalg.h:945` writes only the low 16 bits.

The deletion mark is stored at byte offset 2 in the same 4-byte link header:

- `hnswlib/hnswalg.h:934` to `hnswlib/hnswalg.h:936`.

This is intentional in current hnswlib, and it works with the `M <= 10000` cap, but it is a layout hazard:

- The apparent 32-bit count field really has a 16-bit count.
- The same 4-byte header contains a count, a deletion bit, and unused/reserved space.
- It is endian/layout sensitive and easy to misinterpret in memory analysis or serialization work.

HeapLENS makes this visible as separate `level-0 link count` and `level-0 neighbor ID array` pseudo-regions, but the code-level representation is still a packed header.

## Prefetch Layout Assumptions

Several prefetches read the next neighbor slot without checking whether that slot is logically valid:

- `hnswlib/hnswalg.h:267` to `hnswlib/hnswalg.h:270`
- `hnswlib/hnswalg.h:277` to `hnswlib/hnswalg.h:278`
- `hnswlib/hnswalg.h:371` to `hnswlib/hnswalg.h:374`
- `hnswlib/hnswalg.h:381` to `hnswlib/hnswalg.h:383`

Because the neighbor arrays are allocated at maximum capacity, this usually stays inside allocated memory, and prefetch does not architecturally dereference in the ordinary sense. However, it depends on fixed-capacity layout and can prefetch meaningless addresses for empty lists or the slot after the last logical neighbor.

This is a lower-priority layout assumption, but it matters when changing row padding or neighbor-array layout.

## Benchmark Memory Measurement Confounders

The root `benchmark.py` RSS measurements are process-level measurements, not isolated index-layout measurements:

- `benchmark.py:141` allocates the full NumPy input data matrix.
- `benchmark.py:155` copies data into the HNSW index.
- `benchmark.py:157` records build RSS while the NumPy input is still alive.
- `benchmark.py:177` creates `qdata = data[query_ids]`; because `query_ids` is a list, this uses NumPy advanced indexing and creates a copy.
- `benchmark.py:225` records serialized `index_file_size`, not in-memory footprint.
- `benchmark.py:226` records query RSS while input data, query data, and the index are all alive.

For the HeapLENS trace, the C++ benchmark similarly keeps the 512 MB benchmark input data slab alive throughout build and query. The log shows:

- RSS after data generation: 516,521,984 bytes
- RSS after query ID generation: 517,324,800 bytes
- RSS after build: 3,242,078,208 bytes
- RSS after steady query: 3,699,236,864 bytes

This does not invalidate the layout findings, but RSS should not be interpreted as pure HNSW index layout size.

## Code-Inspection-Only Memory Layout and Ownership Issues

These were not directly exercised by the recorded HeapLENS compact sample, but they are memory-layout or memory-ownership hazards in the project.

### Pickle/introspection path frees `malloc` buffers with `delete[]`

`Index::getAnnData()` allocates buffers with `malloc()`:

- `python_bindings/bindings.cpp:365` to `python_bindings/bindings.cpp:370`

The buffers are then wrapped in capsules that call `delete[]`:

- `python_bindings/bindings.cpp:394` to `python_bindings/bindings.cpp:407`

This is undefined behavior. Use `free()` for these capsules or allocate with `new[]`.

### `setAnnData()` copies unvalidated NumPy byte counts into native layout

`setAnnData()` accepts arrays from a Python dictionary, then copies by `nbytes()`:

- `python_bindings/bindings.cpp:551` to `python_bindings/bindings.cpp:555`
- `python_bindings/bindings.cpp:565`
- `python_bindings/bindings.cpp:577`
- `python_bindings/bindings.cpp:588`

There are layout parameter assertions, but no visible exact-size validation before copying into the native buffers. A malformed pickle/dict can copy too much or too little data into the HNSW layout.

### Brute-force index can misalign labels

`BruteforceSearch` stores `[vector][label]` in one packed byte buffer:

- `hnswlib/bruteforce.h:51` sets `size_per_element_ = data_size_ + sizeof(labeltype)`.
- `hnswlib/bruteforce.h:81` writes the label after vector bytes.
- `hnswlib/bruteforce.h:97` and `hnswlib/bruteforce.h:113` dereference packed label bytes as `labeltype*`.

For odd float dimensions, the label starts at a 4-byte boundary rather than an 8-byte boundary. That is undefined behavior on strict-alignment architectures. HNSW mostly uses `memcpy` for labels, but the brute-force path dereferences.

### Visited-list arrays scale with query concurrency and are absent from the compact sample

`VisitedList` allocates one 16-bit mark per possible element:

- `hnswlib/visited_list_pool.h:8` defines the mark type as `unsigned short int`.
- `hnswlib/visited_list_pool.h:19` allocates `new vl_type[numelements]`.
- `hnswlib/visited_list_pool.h:58` allocates more lists when the pool is empty.

For one million elements, each visited-list mark array is about 2 MB. Multi-threaded search can retain one per concurrent query worker. The HeapLENS type table includes `visited-list mark array`, but the selected compact pages do not include it, so there is no trace-backed alignment finding for this object in this run.

## Recommendations

1. Align level-0 vector payloads to 64 bytes. The trace strongly supports this as the first experiment: it removes the most expensive vector extra crossings.
2. Align or split level-0 neighbor arrays. This avoids 128-byte neighbor arrays spanning three cache lines.
3. Split cold labels out of the hot level-0 row, or place labels in padding created by vector alignment. HeapLENS shows labels mixing with hot row regions.
4. Align upper-link blocks or at least align upper-neighbor arrays. The recorded upper-neighbor arrays are exactly 64 bytes but all sampled whole instances were unaligned.
5. Remove the unused upper-link `+ 1` byte, or account for and serialize it consistently.
6. Add explicit documentation and static assertions around the packed 16-bit link count plus deletion mark.
7. Fix the `malloc()`/`delete[]` mismatch in `python_bindings/bindings.cpp`.
8. Treat `benchmark.py` RSS as process RSS, not index RSS. If index-only memory is needed, subtract retained input/query arrays or run an index-only measurement path.
