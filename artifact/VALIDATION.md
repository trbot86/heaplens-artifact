# Submission validation and limits

Tests below were performed September 22–23, 2026 on x86-64 Windows/WSL2,
inside the supplied Ubuntu 22.04 dependency image. Builds used GCC 11 and
Clang 14.0.6, Python 3.10, and Node 18.18.2. This is **not** the native Linux
paper-performance environment. Some builds overlapped; smoke timings are not
experimental results. Small retained test records are in `validation/`.

## Integration over Sean's September 23 update

The combined tree is based on `5de2274`. A fresh archive extraction (no prior
core builds) passed the dependency/history/export smoke, complete EFRB
instrumentation and conversion, all four EFRB timing variants, and all three
BCCO timing variants. The new database again contained 16,414 records,
including 16,404 typed allocations with source-file metadata. See
`validation/integration-core/` for the logs and small results. These checks
are distinct from the broader pre-integration checks below.

Both RocksDB pairs also passed from that clean extraction: InlineSkipList
baseline versus `ALIGN_TALL_NODE=4 SEG_TALL_NODE=4`, and HashSkipList baseline
versus `REORDER_FIELDS=1 NO_PADDING_NODE=1`. Each built separate binaries,
prefilled 10,000 keys, waited for compaction, and completed a two-second
read-while-writing trial. The compatibility shell entry points were used.
Commands, build logs, source/flag records, binary hashes, and results are in
`validation/integration-rocks/`. These are functionality checks only.

The integrated GUI launcher also started both services: the frontend returned
HTTP 200, both supplied traces were listed, and EFRB initialization returned
seven types, 64 cache sets, and 2,002 cache time rows. This is an HTTP/data-path
check; the interactive browser checks listed below were on the earlier tree.

Sean's spreadsheet, exporter, four RocksDB instrumentation-repair helpers,
and optional native launchers were verified byte-identical to his commit.
The combined RocksDB **diagnostic** pipeline is still unvalidated here;
successful timing runs do not validate its source-instrumentation repairs.

## Pre-integration checks

| Path | Submission check |
|---|---|
| Dependency image | Built successfully from Dockerfile |
| Saved inputs and results | Valkey SQLite integrity, ten saved trials per original Valkey/HNSW variant, retained HNSW factorization analysis |
| Text exporter | Regenerated compact snapshots and analysis from the saved Valkey database |
| GUI, Valkey | Browser checked: trace selection, populated timeline, typed page/object views and cache heatmap |
| GUI, EFRB | Browser checked after file-ID/heatmap fixes: typed pages and node-only occupancy expose one unused set in each group of four in the saved small trace |
| Original HNSW baseline / combined | Both built and ran with 10k 128-D vectors, two threads |
| Valkey baseline / B1C1_64 | Both built; 10k-key preload and three-second two-thread trials; no connection errors or cache misses |
| ASCYLIB EFRB throughput | All four variants built and ran; distinct binary hashes checked |
| ASCYLIB DVY throughput | All four node-size variants built and ran |
| ASCYLIB HJ throughput | glibc and jemalloc variants built and ran |
| TPC-C BCCO | Baseline, segregation, packed-lock variants built and ran with two threads |
| TPC-C EFRB | All five supplied variants built and ran with two threads |
| RocksDB HashSkipList | Baseline and field/alignment variants built and ran with 10k keys and a two-second measured phase |
| Corrected HNSW factorization | Four cells built and ran; one tiny smoke block, not the ten-block full design |
| HNSW separation/alignment | All three cells built and ran; one tiny smoke block, not the six-block full design |

The experiment map in README lists additional drivers, not additional verified
results. In particular, full-scale paper profiles, the complete umbrella run,
and the other fresh diagnostic
trace pipelines have **not** been validated end to end in this submission
environment. Native PMU access, counter fidelity, actual huge-page backing,
and full-scale resource consumption remain to be checked on suitable hardware.

The artifact does not yet automate the complete instrumentation-overhead
table, buffer-wait measurement, every paper plot, or a controlled fresh LLM
comparison. Historical evidence and new measurements are labeled separately.
Fresh LLM runs are optional and were not performed during packaging.

Common expected behavior:

- LLVM instrumentation suggestions appear as warnings; genuine parser/build
  errors now stop execution. Empty databases are rejected.
- First GUI startup compiles the Next.js development UI; allow it to finish.
  Time zero can legitimately show empty pages. Move the timeline.
- Cluster IDs, sampled pages, addresses and HNSW results can vary across runs.
- Performance counters can be unavailable in WSL/VMs. Smoke runs disable
  them and record `NA`; paper-mode failures must not be silently treated as zero.
- Existing legacy output is refused, not overwritten. Use a fresh extracted
  copy for another legacy run; application drivers create unique result folders.
- The inherited instrumentation shell script expects `/root/sifter` inside
  the container. The wrapper supplies this path automatically. Running it
  from an arbitrary in-container path is not supported by this package.
- ASCYLIB's legacy build may print a missing CPU-frequency sysfs warning in
  WSL, and zero-update workloads may print `nan` for insertion/deletion ratios.
  These do not invalidate the search-only functionality check.

An independent clean archive extraction passed the saved-data/export smoke,
both original HNSW variants, and full EFRB instrumentation, execution and
conversion at the documented container path, with no preexisting core builds.
The final EFRB database contains 16,414 records, including 16,404 typed
allocations with source-file metadata.

Before assigning scientific meaning to a new timing, use a dedicated native
host, inspect the recorded environment/placement/workload, run the paper
profile repeatedly, and compare the two variants on that same host.
