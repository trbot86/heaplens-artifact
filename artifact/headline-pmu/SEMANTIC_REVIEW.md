# Measurement semantics review

Author-side review, October 3, 2026 (Toronto). No new measurements. This record
separates source observations from the completed 400-cell measurement audits.
It is not a proof of exhaustive allocation interception or causal attribution.

## Counter and wait boundaries

| Family | Counter interval and denominator | Wait interpretation |
| --- | --- | --- |
| ASCYLIB | Gates after all prefills, before releasing the operation barrier; closes after all operation loops, before teardown. Actual summed search/insert/remove operations. | Worker TLS phase 1 surrounds operation loops. Barrier/gate costs may be in process counters but not loop-local wait intervals. Both arms use identical dynamic SSMEM, unlike the earlier static-link throughput campaign. |
| TPC-C | `macrobench/system/main.cpp` enables before measured pthread creation and disables after joins. Actual recorded transaction counts. Warmup is outside. | `f_real` brackets worker `run()` with phases 1/2. Thread creation, joins and terminal worker logging can fall inside PMU but outside phase-1 waits. BCCO uses jemalloc; EFRB uses mimalloc with the recorded DEBRA/record-manager flags. |
| RocksDB HSL/ISL | Only `readwhilewriting` is gated: enable before `shared.start`, disable after `shared.num_done`. PMU covers the process, including writer and background work. Denominator is actual reader operations, not total reader+writer operations. | Benchmark workers are phase-marked. Background workers remain phase 0; phase 0 must not be described as exclusively initialization, and phase-1 sums must not be called whole-process logging waits. |
| Valkey | Server and inherited threads, excluding the separate memtier process. Gate encloses measured client startup/load/teardown after 4M-key preload. Denominator is memtier's actual completed `Count`, not configured duration times a rounded rate. | Persistent producer wait intervals are classified after closing the gate against conservative enclosing monotonic timestamps. Start counts use half-open window membership; durations use overlap. These are enclosing bounds, not exact kernel PMU transition times. Terminal publication/drain occurs after disabling PMU. |
| HNSW | Five gated Python `knn_query` calls, each 100K queries; denominator 500K. Build, 10K-query warmup and Python recall calculation are excluded. | Each ParallelFor call creates fresh workers: 120 measured query producers. Thread lifecycle/TLS flushing can be inside PMU but outside phase-1 work. Main-thread/background phase 0 is not an exhaustive process-wide query classification. |

Source evidence: local `prepare_ascylib.py`, `prepare_tpcc.py`,
`prepare_rocks.py`, `rocks_measurement.py`, `run_valkey.py`,
`valkey_protocol.py`, `valkey_control_overlay.py`, `valkey_readiness_drain.py`,
`hnsw_phase_overlay.py`, `overhead-wait-probe.h`, and `wait_events.h`.
Actual retained TPC-C main.cpp lines 168–178 confirm creation/join enclosure.
Actual RocksDB db_bench_tool.cc lines 4058–4066 confirm start/completion gates;
ReadWhileWriting sends thread 0 to BGWriter, whose stats are excluded from merge
(line 7053). These locations are under the frozen Pyke build directories.

## Typed allocation scope

- HSL's optimization changes `SkipList` bucket-object field order, not its
  per-key Node definition. The actual logging hash_skiplist_rep.cc placement
  construction is wrapped in MemStamp; memhook_interface.h lines 141–163 record
  its pointer, `sizeof(T)` and `typeid(T)`. The retained runtime dictionary
  includes `rocksdb::SkipList<char const*, rocksdb::MemTableRep::KeyComparator const&>`.
  In contrast, skiplist.h lines 213–222 allocate Node storage through an
  unannotated arena call and placement-new. Do not claim every HSL arena node is
  separately typed. Dictionary presence is not an allocation-frequency estimate.
- ISL preparation explicitly applies `rocksdb_inline_regions.py`; the retained
  before runtime dictionary contains the InlineSkipList Node and atomic link
  types. Region annotations and allocator events must not be added together as
  disjoint physical heap bytes without deduplicating overlapping regions.
- Valkey preserves jemalloc and the before/after allocator wrappers. All 20
  completed logging cells have full typed scans and positive robj counts; counts
  reconcile to receipts. That demonstrates observed semantic-object coverage,
  not coverage of every possible Valkey allocation path.
- HNSW records graph/vector/link/label regions, visited-list objects and mass
  arrays. Actual hnswalg.h lines 1550–1567 show overlapping element/subregion
  annotations. All 40 full typed scans have 1M VectorPayload records and nonzero
  VisitedList, VisitedMass and QueryScratch records.
- HNSW QueryScratch is a dynamic searchKnn C++ new/new[] context with a recursion
  guard, not an exact STL queue type. It preserves the underlying allocation
  implementation. Do not describe it as exhaustive Python/NumPy allocation
  capture, and do not interpret annotated-region totals as unique malloc bytes.

## Claims permitted by current checks

The measurement audit establishes the intended 400 identities and retained
counts/counters/windows/waits, with preserved invalid attempts and no favorable
selection. It does not establish that overhead is solely caused by buffer waits:
the logging arm also includes allocation instrumentation, output and wait-probe
cost. Summed per-thread wait durations are thread-time, not wall-clock delay;
overlapping waits cannot be subtracted directly from wall time. PMU differences
are observational and do not by themselves isolate a hardware mechanism.

Keep these two-pass results separate from the earlier headline throughput study.
In particular dynamic SSMEM, both-arm RTTI for RocksDB, and the explicitly wider
process-counter intervals must remain visible in any comparison.

## Cross-variant checks and completion

Actual ISL before/after inlineskiplist.h lines 826–848 preserve the selected
arena/alignment branch and record the link-prefix region plus Node/key region.
Actual optimized Valkey object.c lines 55–66 call the optimized
zmallocRobjUsable first and then record its returned pointer; zmalloc.c lines
473–507 retain free hooks before the existing free implementation. No allocator
replacement was introduced merely to simplify logging.

The ASCYLIB retained EFRB logging source uses typed `ssmem_alloc_s` for node_t
and info_t. The preparation recipe applies source instrumentation to all tree
variants and verifies dynamic SSMEM linkage; final audits verify binary/allocator
hashes. HJ before/after is an allocator comparison: before preloads jemalloc,
after does not. It is not a field-layout change. TPC-C instrumentation preserves
the variant-specific allocator and compile flags enumerated in prepare_tpcc.py.

This completes the bounded source-path interpretation review needed for the
reported PMU/wait comparisons. It does not certify exhaustive allocation-path
coverage across these applications. Runtime dictionaries alone are not a full
typed-count audit for ASCYLIB/TPC-C/RocksDB; full typed-count reconciliation was
performed for HNSW and Valkey. Keep that evidence distinction explicit.

The numerical summary in FINAL_RESULTS.md and campaign-numerical-summary.json
retains all400cells, mean/sample-SD/range statistics, all four normalized counters,
and scoped reuse waits. Independent PowerShell calculations reproduced all20
throughput-loss ratios; the summary identity set matches the final reconciliation.
No additional measurement was run for this review.
