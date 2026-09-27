# Source and result provenance

This package extends Sean Ovens's `atc2026-artifact` branch at
`5de2274b687406d638ff8f8f248da39b48284a21`. Additions initially prepared on
`7a384f36954300c5dc86d7f95d47279a2c5b1ad6` were integrated over that newer commit.
No historical remote tree was modified
while preparing it. `historical/` contains recorded evidence, not output from
the submission smoke tests. `results/` is reserved for new runs.

## Components

| Component | Source |
|---|---|
| HeapLENS instrumentation, logger, converter, sampler, GUI | Sean's artifact commit above |
| Text exporter and snapshot analyzer | Authors' source-only ZIP `heaplens-source-2026-09-22.zip`; SHA-256 `b66dd16d88b0330b4b0e13c8f84b5b701bb06843b89854dee27d4db9f80c8ce9` |
| ASCYLIB | Upstream commit `3c2d1a231eac3518a4167d7d4a709cb22a3cff6b` plus `patches/ascylib-historical.patch`, recovered from the authors' experiment tree |
| ssmem | Source commit `68f0dad3e1be58e2d845f3e028039edb448812f0`; rebuilt for x86-64 scratch copies |
| SetBench | `5b574d4`; recordmgr `fee54cd`, tools `643ad58`; Sean's `patches/setbench-tpcc/` overlay |
| RocksDB diagnostic source | `7e272d20329449a7eb8d158d283e1635d029909a`, immediately before the upstream bucket-field reorder |
| RocksDB historical performance source | `19e4aba3db75bd6add7177164c892ab6cdfd50b3` plus `patches/rocksdb-historical.patch` |
| Valkey baseline | Tracked files from the saved baseline variant in `valkey_bench_opt_after_heaplens_pyke`; associated checkout revision `c8c38e778b00f567245009269a8019c634179ba5` |
| Valkey optimized | `patches/valkey-B1C1_64.patch`, exact textual difference between saved baseline and B1C1_64 variants; changes `src/object.c` and `src/rax_malloc.h` |
| memtier | `c3546a4b7a60a759e19d968e0976b835886cd544` |
| HNSWLib original experiment | Source snapshot from `hnswlib_bench_opt_after_heaplens_jax2`; compile-time switches retain the original experimental variants |
| HNSWLib corrected huge-page factorization | Source commit `8b2ac235017d7963ca237d9a523689538b121c32`; 40 retained trials |
| HNSWLib separation/alignment follow-up | Source commit `472502feb6a2ba8444d2f3ec03fe9f2a01db87a3`; 18 retained trials |

The package manifest identifies exact distributed files. A snapshot of an
experimental working tree is not claimed to be identical to pristine upstream
merely because its parent revision is known. Upstream licenses remain in each
vendor tree; HeapLENS's root license is GPLv3. Vendored allocator binaries in
SetBench are retained from the pinned upstream tree; `lib/versions.txt` records
available version information (not every binary has a recorded version).

### TPC-C allocator packaging correction

Artifact preparation inadvertently changed the `MEMHOOK_SEG_DS` library path
to the same jemalloc library used by process-wide `LD_PRELOAD`. Reopening that
library did not create a separate allocator, removing the intended separation
between tree objects and other database allocations in the jemalloc runs.
The retained experiment code instead selected a distinct jemalloc library.

The corrected drivers stage that retained jemalloc 5.3.0 binary from
`vendor/heaplens-allocators/` separately from SetBench's process-wide jemalloc
5.0.1 or mimalloc 1.6.3. Its checksum and license accompany the binary. The
allocator now rejects a configuration that resolves both paths to the same
`malloc` function. This corrects an error introduced during artifact packaging;
it is not a new optimization or a change to the retained paper results.

## Saved inputs and measurements

Sean's `data/paper_data.xlsx` and its accompanying README are retained from
commit `5de2274`. They cover ASCYLIB, TPC-C, RocksDB, and overhead measurements;
the HashSkipList sheet was subsequently checked as described below.
The four RocksDB instrumentation-repair helpers and optional
native GUI/export launchers from his update are also retained.

RocksDB uses 32-byte keys and 128-byte values, as in accepted-paper Section 6.4
and the `pyke RocksDB HSL` workbook labels. The surviving
`run_experiment_asplos.sh.txt` instead selects 64/256-byte sizes and is not
the launch record for those workbook rows.

HashSkipList's artifact defaults are corrected to the workbook's 96-thread,
10M-key, 256-MiB configuration and `b_reorder_fields` versus `a_default`
comparison: field reordering only, without the separate `NO_PADDING_NODE`
change. The verified protocol uses 95 readers plus one writer, both sockets
with SMT and interleaved memory, a 10-second read window after initial
compaction completes, and disabled WAL but enabled flushing/compaction.
The release/portable build and retained jemalloc 5.3 allocator are unchanged.
This corrects artifact configuration; it adds no optimization to RocksDB.
The workbook gives +8.28%; a five-pair release-build confirmation gives +7.51%.
The complete historical build/launch environment has not been recovered; see
[configurations and batch variability](REPRODUCTION_CONFIGURATIONS.md#rocksdb-hashskiplist-field-reordering).

InlineSkipList retains its separately confirmed 20-physical-core, 60-second,
jemalloc 5.3, threshold-3 memory-only configuration. Its 46.5-GiB write buffer,
disabled WAL/automatic compaction/shutdown flushing, and per-trial checks
ensure no user-data persistence; metadata and diagnostic writes remain.
The two experiments do not share a persistence policy. Historical data are
unchanged. The restored patch implements `REORDER_FIELDS`,
`NO_PADDING_NODE`, `ALIGN_TALL_NODE`, and `SEG_TALL_NODE`; passing these names
to the unpatched diagnostic-source revision would not enable the optimizations.

Valkey: twenty `summary.json` records (ten baseline, ten B1C1_64) from the
`noperf_stability_K4M_G4S1_*` campaign, including configurations, throughput,
latency, memory, and connection-error counts. These are the original 4M-key,
24+24-thread, cross-NUMA measurements. The ratio of throughput means is about
+4.23%. The saved **diagnostic trace is a different run**: a 1M-key preload,
sample proportion 0.1, recorded pages-per-type setting 2. Its exact metadata
is in `data/valkey/benchmark_config.json`; do not describe it as the 4M-key
performance run or silently relabel its settings.

HNSWLib: ten baseline and ten combined trials from the original 768-D campaign.
The ratio of QPS means is about +6.17%; averaging trial-wise ratios is a
different statistic. The original implementation issued huge-page advice
after touching the vector slab. These retained data and source remain unchanged;
`hnsw --profile paper --hnsw-source original --dim 768` selects that implementation
and workload. The default `hnsw --profile paper` instead uses the existing
corrected snapshot (advice before first touch) at both 128 and 1536 dimensions,
matching the revised paper configurations. Results for these configurations
are listed separately in [Reproduction configurations](REPRODUCTION_CONFIGURATIONS.md).

Historical scripts stored as `.txt` are evidence only. They may contain
machine-specific paths or administrative commands; do not execute them.
The artifact runners do not change ASLR, THP policy, CPU governors, sysctls,
host storage, or other users' processes.

EFRB: `data/efrb/allocs.sqlite` is a newly generated illustrative trace from the
submission smoke test, not the database used for the paper's screenshot. It
contains 16,414 allocation records; its accompanying README records settings.

## Packaging changes

- Added a dependency container, unified entry point, exporter, application
  before/after drivers, retained inputs, historical evidence, and guides.
- Restored ASCYLIB's missing experimental flags/implementations in scratch
  copies. They must not be treated as no-op flags on pristine upstream.
- Added an instrumentation-only compatibility patch removing casts from
  inline-assembly output lvalues, which Clang 14 otherwise rejects.
- Made instrumentation errors fail the pipeline, and reject empty allocation
  databases. These are validation changes, not new performance measurements.
  Expected instrumentation fix-it messages are warnings, while genuine
  compiler/parser errors propagate as failures.
- Restore the file ID assignment in `MEMHOOK_LOG_C_ALLOC`. Without it,
  ASCYLIB suballocation records have missing source-file metadata and are
  discarded by the GUI. This affects newly generated diagnostic traces;
  the retained historical inputs are not rewritten.
- Retain whole-process hardware-counter totals and normalize them by actual
  measured operation counts (committed transactions for TPC-C), including
  setup/teardown costs in the numerator. This corrects the original
  count/throughput denominator; historical paper results were not rewritten.
  See the README errata for the affected experiments.
- Use `s=1` for newly generated diagnostic databases. The historical trace
  metadata remains unchanged. Do not infer a study of arbitrary `s` from this.
- Disable Next.js telemetry and replace the build-time Google-font download
  with the existing CSS/system-font stack. No reviewer activity is collected.
- Include per-type visibility in the heatmap's memoization dependencies, so
  selecting a type immediately recomputes occupancy rather than leaving stale
  colors until a different cache/view is selected.

New benchmark runs use the packaged container's compiler/libraries, not an
asserted replica of every historical host. Record the environment and compare
within-host variants; exact percentages are hardware/environment dependent.
