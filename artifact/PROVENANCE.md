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

## Saved inputs and measurements

Sean's `data/paper_data.xlsx` and its accompanying README are retained from
commit `5de2274`. They cover ASCYLIB, TPC-C, RocksDB, and overhead measurements;
the workbook's numerical contents were not independently audited during this
integration. The four RocksDB instrumentation-repair helpers and optional
native GUI/export launchers from his update are also retained.

RocksDB workload discrepancy: the retained `run_experiment_asplos.sh.txt` uses
64-byte keys and 256-byte values, whereas accepted-paper Section 6.4 says
32-byte keys and 128-byte values. New runs default to the retained script;
`--rocks-key-size 32 --rocks-value-size 128` selects the sizes in the prose.
Both are explicit, recorded configurations, not an assertion that this
discrepancy has been resolved. The restored patch implements `REORDER_FIELDS`,
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
after touching the vector slab. This replay deliberately preserves that
implementation, and does **not** establish actual huge-page backing or
reproduce the later corrected factorization by substitution.

Historical scripts stored as `.txt` are evidence only. They may contain
machine-specific paths or administrative commands; do not execute them.
The artifact runners do not change ASLR, THP policy, CPU governors, sysctls,
host storage, or other users' processes.

EFRB: `data/efrb/allocs.sqlite` is a newly generated teaching trace from the
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
- Report whole-process hardware counters as **raw totals**, not events per
  operation. The existing helper's count/throughput normalization was not
  dimensionally events/operation; historical paper results were not rewritten.
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
