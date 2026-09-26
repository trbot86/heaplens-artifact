# HeapLENS — ACM ATC 2026 artifact

**Paper:** *HeapLENS: Heap Layout Evaluation & Navigation Suite*, ACM ATC 2026,
paper 483. This artifact supplies the C/C++ instrumentation, allocation logger,
trace reconstruction and sampling, interactive GUI, text exporter, application
inputs/results, and before/after experiment scripts.

## 1. Requirements and installation

Use x86-64 Linux with Docker Engine. Run the commands below in a Linux shell
from the repository root. The artifact was tested with Docker Engine 29.4.0
and Docker CLI 26.1.3.

Plan for roughly 20 GB of free disk space for the dependency image and small
builds, and 8–16 GB RAM for basic checks. Use at least 32 GB RAM and additional
scratch disk for the full application experiments; full TPC-C runs and large
traces can require substantially more. Builds use four jobs by default;
reduce `--jobs` if memory is limited.

The source archive includes vendor content. For a Git checkout, initialize
the pinned submodules before building:

```bash
git submodule update --init artifact/vendor/ascylib artifact/vendor/setbench artifact/vendor/rocksdb
git -C artifact/vendor/setbench submodule update --init common/recordmgr tools
```

Build the dependency image:

```bash
bash artifact/run.sh build
```

The container uses Ubuntu 22.04, LLVM/Clang 14.0.6, Python 3.10, Node 18.18.2,
and pinned direct Python/npm dependencies. Its first build needs Internet
access to package registries and normally takes several minutes. The runner
mounts this repository at `/root/sifter` inside the container.

## 2. Try HeapLENS

```bash
bash artifact/run.sh smoke
bash artifact/run.sh gui
```

`smoke` checks dependencies and SQLite integrity, recomputes summaries of
saved results, and regenerates the LLM text export. Expected output includes
`Python imports OK`, ten saved runs per Valkey/HNSW variant, `Export OK`,
and a new results directory. With the image built, this normally finishes
in under a minute.

For the GUI, open <http://localhost:3000>, choose `valkey-artifact.sqlite`,
and follow [GUIDED_WALKTHROUGH.md](GUIDED_WALKTHROUGH.md). Move the timeline
away from its initially empty time. The GUI also lists `efrb-smoke.sqlite`,
a small illustrative trace. The servers bind to the host's loopback interface;
Ctrl-C stops them.

To build and run small versions of the application benchmarks:

```bash
bash artifact/run.sh hnsw --profile smoke
bash artifact/run.sh valkey --profile smoke
```

These compile separate baseline and optimized versions. Valkey uses 10,000
synthetic keys, two server/client threads, and three timed seconds per variant.
HNSW uses 10,000 128-D vectors and 1,000 queries. Builds take minutes.
Smoke speedups are not paper evidence.

## 3. Run the performance experiments

Use `--profile paper` for the full workloads; the default is `smoke`.
Paper-mode runs use ten repetitions per variant by default; `--reps N`
changes the repetition count. The HNSW attribution experiments in Section 4
have their own repetition schedules.

### Run an individual experiment

Each command below builds and runs all variants for the named experiment
and prints a throughput comparison. For `experiment NAME`, names ending in
`_bench` measure performance. The other names instrument the application and
generate allocation-trace databases for the HeapLENS GUI (see Section 6).

```bash
# ASCYLIB trees: EFRB (§6.2), DVY and HJ (Appendix B)
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_efrb_bench --profile paper
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_dvy_bench --profile paper
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_hj_bench --profile paper

# TPC-C indexes (§6.3)
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment tpcc_bcco_bench --profile paper
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment tpcc_efrb_bench --profile paper

# RocksDB memtables (§6.4)
HEAPLENS_NUMA=1 bash artifact/run.sh rocksdb --memtable prefix_hash --profile paper
HEAPLENS_NUMA=1 bash artifact/run.sh rocksdb --memtable skip_list --profile paper

# Valkey (§6.5 / Appendix D) and HNSWLib (Appendix D)
HEAPLENS_NUMA=1 bash artifact/run.sh valkey --profile paper
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw --profile paper
```

The section references use the accepted submission's numbering.

For the confirmed eight-thread EFRB, 24-thread HJ, and 128-D/1536-D HNSW
configurations, see [Reproduction configurations](REPRODUCTION_CONFIGURATIONS.md).
That guide gives complete commands, measured improvements and the corresponding
machines. These additional recipes do not replace the stored paper data.

ASCYLIB and TPC-C build and save all variant binaries before measuring them.
Repetitions are interleaved, with one run of each variant per round and rotating
run order. RocksDB likewise builds both variants first and alternates their
order. `--trial-order blocked` instead runs all repetitions of each variant
together.

HNSW likewise builds separate variant modules before timing, then interleaves
fresh processes. Its factorization commands use the fixed orders in Section 4.

| Experiment | Variants compared |
|---|---|
| ASCYLIB EFRB | Baseline, object segregation, parallel prefill, both |
| ASCYLIB DVY | 96/72/128/192-byte node layouts |
| ASCYLIB HJ | glibc malloc / jemalloc backing the suballocator |
| TPC-C/BCCO | Baseline, node segregation, segregation + packed row lock |
| TPC-C/EFRB | Allocator, row-padding, and reclamation variants |
| RocksDB HashSkipList (`prefix_hash`) | Baseline / field reorder + node-alignment reduction |
| RocksDB InlineSkipList (`skip_list`) | Baseline / alignment and separation of tall nodes |
| Valkey | Baseline / B1C1_64 small-object placement patch |
| HNSWLib | Packed layout / separate aligned vector slab + huge-page advice |

### Run all nine experiments

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh all-performance --profile paper
```

This runs the nine groups listed above sequentially. Allow many hours and
substantial scratch disk space. To include the two HNSW attribution
experiments, also run the commands in Section 4.

### Hardware and workloads

The paper describes a dual-socket system with two 24-core Intel Xeon Gold
5220R CPUs and 186 GiB DRAM.

Valkey uses two NUMA nodes with 24 available physical cores each, 4M keys,
128-byte values, 20% SET/80% GET, pipeline 16, four clients/thread, and
30-second measurements after preload. Server and client nodes default to
0 and 1; `--server-node` and `--client-node` select them. Persistence is off;
networking is loopback, so a physical NIC is not required.

HNSW uses 1M 768-D vectors, 100k indexed queries, 24 build/query threads,
M=16, ef_construction=200, ef=64, k=10, 10k warmup queries, and five timed
iterations. Allow hours for repeated fresh graph constructions. The output
includes QPS and `recall_mean`. The latter measures indexed queries finding
their own label; it is not ground-truth top-k ANN recall. `--dim` changes the
dimension; `--threads` changes both construction and query threads. `hnsw`
defaults to the original source snapshot; `--hnsw-source corrected` selects
the existing snapshot that issues huge-page advice before first touch.

RocksDB uses 17 reader threads plus a background writer, 10M keys, 64-byte
keys, 256-byte values, 128 MiB write buffers, disabled WAL, and a 10-second
measurement phase. `--rocks-key-size` and `--rocks-value-size` override the
key and value sizes. Each trial creates a fresh database in its results
directory.

For ASCYLIB, TPC-C, RocksDB, and HNSW, paper-mode runs select one available hardware
thread per physical core on `--server-node` (default 0), and bind memory to
that node. CPU IDs are discovered from the host's topology and allowed CPU set;
they are not assumed to match the paper's machine. `--threads N` changes the
worker count (readers plus writer for RocksDB; build/query threads for HNSW). `--cpus 0-7` or
`--cpus 0,2,4,6` explicitly selects that many distinct physical cores on the
chosen node. TPC-C pins individual workers; ASCYLIB, RocksDB and HNSW run within the
selected CPU set. `--memory-policy interleave` selects the earlier single-node
interleave policy instead of strict binding. Small smoke runs omit NUMA
placement unless `--cpus` or `--memory-policy` is supplied.

ASCYLIB also accepts `--initial`, `--range`, `--duration-ms`, and `--update-pct`.
Use these command-line options rather than outer-shell `THREADS=...` or
`INITIAL=...` assignments: the options pass through the Docker wrapper.
For example, run the additional eight-thread EFRB configuration used in our
reproduction checks:

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_efrb_bench \
  --profile paper --threads 8 --initial 262144 --range 524288 \
  --duration-ms 5000 --reps 10 --server-node 0 --memory-policy bind
```

ASCYLIB rounds non-power-of-two initial sizes upward. The default EFRB command
above remains 24 threads, 262,144 initial keys, and 5,000 ms. DVY and HJ default
to eight threads, 1,048,576 initial keys, and 5,000 ms. All three default to
search-only workloads; the default key range is twice the rounded initial size.

Section 6.3 already describes the TPC-C/EFRB reclamation fix: use one EBR
instance shared across the database tables, instead of a separate instance
for each table, to address the observed accumulation of retired-object blocks.
The artifact's existing `MACROBENCH_SINGLE_RECMGR` option selects this fix.
TPC-C/EFRB's combined improvement is `e_single_recmgr_mimalloc_fixed` versus
`b_mimalloc`: shared reclamation plus row padding, with mimalloc and separate
tree allocation held fixed. `d_single_recmgr` versus `a_jemalloc` isolates
shared reclamation with jemalloc. The historical `c_mimalloc_fixed` versus
`b_mimalloc` comparison also removes tree segregation, so it does not isolate
row padding. The summary identifies these comparisons explicitly.

The allocator choices are retained: TPC-C uses the bundled process-wide
jemalloc or mimalloc, plus a distinct jemalloc library for segregated tree
allocations. HJ defaults to the retained jemalloc 5.3 library;
`--hj-jemalloc 5.0` selects SetBench's bundled version for comparison.
RocksDB continues to use SetBench's bundled process-wide jemalloc.
Process-wide allocator paths and hashes are recorded
for ASCYLIB and TPC-C trials; see [allocator provenance](vendor/heaplens-allocators/README.md).

`HEAPLENS_NUMA=1` permits NUMA placement by relaxing the container's seccomp
filter. `HEAPLENS_PERF=1` grants the PERFMON capability for hardware counters;
the host must also permit PMU access. For throughput-only ASCYLIB/TPC-C runs,
add `PERFBENCH_PERF=off` before the command, for example:

```bash
PERFBENCH_PERF=off HEAPLENS_NUMA=1 bash artifact/run.sh experiment tpcc_bcco_bench --profile paper
```

## 4. Attribute the HNSWLib improvement

Two experiments separate the contributions of the HNSWLib layout changes
and huge-page advice:

- Layout versus huge pages: run the packed baseline, separation + alignment,
  huge-page advice alone, and both changes together. This measures their
  individual contributions and interaction. The paper profile runs ten
  repetitions of each of the four variants, interleaving their order.
- Separation versus alignment: compare the packed layout, a separate vector
  slab offset by 32 bytes, and the same slab aligned to 64 bytes. The paper
  profile runs six repetitions of each variant, covering all six run orders.

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw-factorization --factors hugepage --profile paper
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw-factorization --factors alignment --profile paper
```

These commands use separate source snapshots. The huge-page experiment
issues advice before first touch. Check live mappings for transparent
huge-page backing when interpreting this comparison.

The recorded 40-trial and 18-trial datasets are in
`artifact/historical/hnsw-factorization/` and
`artifact/historical/hnsw-alignment/`. They were collected on the dual-socket
Xeon Gold 5220R machine described in the paper (host name `pyke`), using
Ubuntu 24.04 and GCC 13.3.

## 5. Find and interpret results

Valkey, HNSWLib, RocksDB, and HNSW attribution runs write to
`artifact/results/<command>-<UTC timestamp>/`. Each directory contains
configuration/environment records, build logs, per-run data, and summaries.
`--out /root/sifter/artifact/results/NEW_NAME` selects a specific new directory.

ASCYLIB and TPC-C runs write `results.tsv`, `summary.txt`, and per-run logs
under `artifact/experiments/<name>/`. `protocol.json` records the selected
workload and placement; `runs/campaign.json` records commands, saved binary
hashes, and allocator paths/hashes. `runs/execution.json` records trial order.
Saved executables and build logs are in `runs/binaries/`; each trial also has
a command/environment record and raw stdout/perf logs. The summary reports
mean throughput, standard deviation, and percentage changes for the named
comparisons. The `*_raw` columns
in `results.tsv` are whole-process performance-counter totals, including
initialization/prefill and teardown. The `*_per_op` columns divide these totals
by `operation_count`: measured tree operations for ASCYLIB, or committed
transactions for TPC-C, as identified by `operation_unit`. Throughput is in
operations/second (transactions/second for TPC-C).

The named `experiment` scripts use fixed build/output directories and refuse
to overwrite an earlier run. To repeat one of these experiments (for example,
after a smoke run), keep the previous copy and use another extraction or
checkout of the artifact. Reuse the Docker image; it need not be rebuilt.
Valkey, HNSWLib, and RocksDB commands create new directories automatically.

### Saved experimental data

The following files contain saved experimental measurements and configurations,
separate from the outputs of new runs described above. `artifact/historical/`
holds application results, HNSWLib attribution data, and original run scripts.

| Location | Contents |
|---|---|
| `artifact/data/paper_data.xlsx` | Per-run measurements and aggregate tables for ASCYLIB, TPC-C, RocksDB, and instrumentation overhead; see the [sheet guide](data/README.md) |
| `artifact/historical/valkey/` | Ten baseline and ten optimized runs: JSON measurements and configurations for the Valkey experiment |
| `artifact/historical/hnswlib/` | Ten baseline and ten optimized HNSWLib runs in CSV form, plus comparison summaries |
| `artifact/historical/hnsw-factorization/` | Forty trials separating layout changes, huge-page advice, and their interaction, as described in Section 4 above |
| `artifact/historical/hnsw-alignment/` | Eighteen trials separating vector separation from alignment, as described in Section 4 above |
| `artifact/historical/ascylib/`, `artifact/historical/rocksdb/` | Original experiment scripts; measurements for these experiments are in the workbook |

The JSON and CSV results retain per-run measurements; the HNSWLib attribution
directories also include benchmark logs and analysis summaries. Original scripts
stored as `.txt` are for reference; use the commands above to run experiments.

To recompute the saved Valkey/HNSWLib throughput comparisons and the
layout-versus-huge-pages analysis:

```bash
bash artifact/run.sh history
```

## 6. Generate traces and try model-assisted analysis

For `experiment NAME`, names without `_bench` generate instrumented allocation
traces for the GUI.
For example, to generate a small EFRB trace:

```bash
bash artifact/run.sh experiment ascylib_efrb --profile smoke
```

The trace-generation names are `ascylib_efrb`, `ascylib_dvy`, `ascylib_hj`,
`tpcc_bcco`, `tpcc_efrb`, and `rocksdb_hsl`. Their generated SQLite databases
are written under `artifact/experiments/<name>/`. Trace generation is
separate from the uninstrumented performance experiments above.

For a guided Valkey LLM example, follow [LLM_EXAMPLE.md](LLM_EXAMPLE.md).
It includes the saved input and optimization patch, plus prompts for a
fresh model-assisted run. To regenerate the text input from the supplied trace:

```bash
bash artifact/run.sh export
```

## Errata

**TPC-C artifact packaging.** The initial artifact inadvertently pointed the
tree-segregation allocation path at the process-wide jemalloc library. Loading
that same library again did not provide a separate allocator. The corrected
drivers restore the distinct jemalloc library used by the retained experiments
and reject accidental reuse of the global allocator. This was introduced during
artifact preparation; the retained paper results are unchanged. See
[allocator provenance](vendor/heaplens-allocators/README.md).

**Counter normalization.** The original ASCYLIB (EFRB, DVY, HJ) and TPC-C
(BCCO, EFRB) scripts inadvertently divided cache/TLB miss and context-switch
counts by throughput rather than operation/transaction counts. This artifact
uses the actual counts and retains the raw counters. Corrected per-operation
values therefore differ from those in the paper. Throughput measurements and
speedups are unaffected. Relative counter changes are preserved when measurement
durations match, apart from rounding; they require recalculation for
variable-duration TPC-C runs. The supplied workbook preserves the original data.

**Valkey improvement.** The maximum throughput improvement is 5.9%;
the paper's inconsistent reference to 6.2% is incorrect.
