# HeapLENS — ACM ATC 2026 artifact

**Paper:** *HeapLENS: Heap Layout Evaluation & Navigation Suite*, ACM ATC 2026,
paper 483. This artifact supplies the C/C++ instrumentation, allocation logger,
trace reconstruction and sampling, interactive GUI, text exporter, application
inputs/results, and before/after experiment scripts.

## 1. Requirements and installation

Use x86-64 Linux with Docker Engine. Run the commands below in a Linux shell
from the repository root. The artifact was tested with Docker Engine 29.4.0
and Docker CLI 26.1.3.

Hardware-counter runs with `HEAPLENS_PERF=1` require a Docker host running
Linux kernel 5.8 or newer and a Docker runtime that supports `CAP_PERFMON`.
This capability was [introduced in Linux 5.8](https://man7.org/linux/man-pages/man7/capabilities.7.html).
The runner does not fall back to the broader `SYS_ADMIN` capability. For
an older kernel on a trusted evaluation host, an administrator may edit
`artifact/run.sh`, replacing `--cap-add PERFMON` with `--cap-add SYS_ADMIN`
and removing the kernel-version guard in the `HEAPLENS_PERF` block.
This grants substantially broader privileges; host perf restrictions may
still apply. For
throughput-only runs on older hosts, omit `HEAPLENS_PERF=1` and set
`PERFBENCH_PERF=off`. GUI and trace inspection do not require this capability.

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

DVY additionally includes an isolated Ubuntu 24.04 libc/loader in that same
image; it needs no corresponding installation on the host. Only DVY uses
this runtime. Rebuild the image after updating these scripts. Other experiments
retain their existing runtime, allocator and huge-page settings.

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

For remote use, forward both the frontend and backend ports from your local
machine, then open <http://localhost:3000> locally:

```bash
ssh -L 3000:localhost:3000 -L 5000:localhost:5000 host
```

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

### Table 1 case-study map

The rows below follow the application/data-structure rows of paper Table 1.
Performance commands build and compare the variants listed; diagnostic commands
generate fresh instrumented traces, not performance measurements. Use the same
diagnostic profile on both sides. Smaller traces may not exhibit a phenomenon
that depends on the paper's thread count or working-set size.

#### Performance comparisons

| Table 1 case | Numerical reproduction command | Compared variants / effective change |
| --- | --- | --- |
| ASCYLIB/EFRB | `experiment ascylib_efrb_bench --profile paper` | `a_default` through `d_both`; `SEG_OBJS=1`, `INIT=all` separately and together |
| ASCYLIB/DVY | `experiment ascylib_dvy_bench --profile paper` | 96/72/128/192-B nodes; `DRACHSLER_PAD=0/128/192`; equal huge-page policy |
| ASCYLIB/HJ | `experiment ascylib_hj_bench --profile paper` | retained jemalloc 5.3 / glibc malloc |
| TPC-C/BCCO | `experiment tpcc_bcco_bench --profile paper` | `a_default`, `b_seg_ds`, `c_seg_ds_pack_lock`; `MEMHOOK_SEG_DS`, then `MACROBENCH_PACK_LOCK` |
| TPC-C/EFRB | `experiment tpcc_efrb_bench --profile paper` | `b_mimalloc` / `e_single_recmgr_mimalloc_fixed`; shared reclamation + padded rows, allocator/segregation fixed |
| RocksDB/HashSkipList | `rocksdb --memtable prefix_hash --profile paper` | default / `REORDER_FIELDS=1`, 56-B to 48-B bucket layout |
| RocksDB/InlineSkipList | `rocksdb --memtable skip_list --profile paper` | baseline / alignment + segregation, thresholds 3 |
| Valkey/string cache | `valkey --profile paper` | baseline / `patches/valkey-B1C1_64.patch` |
| HNSWLib | `hnsw --profile paper` | packed / separate aligned vectors + huge-page advice, at both 128 D and 1536 D |

Prefix numerical commands with `HEAPLENS_NUMA=1 bash artifact/run.sh`;
ASCYLIB/TPC-C hardware counters additionally require `HEAPLENS_PERF=1`.
For example, `HEAPLENS_NUMA=1 bash artifact/run.sh hnsw --profile paper --dim 128`
runs only the requested 128-D comparison. Counter-free ASCYLIB/TPC-C runs use
`PERFBENCH_PERF=off`. Detailed workloads and placement rules follow below.

#### Before/after visualization

To use the short commands in this table, define this shell helper
once from the repository root:

```bash
trace() {
  case "$2" in
    before) variant=baseline ;;
    after) variant=optimized ;;
    *) echo 'Use: trace NAME before|after' >&2; return 2 ;;
  esac
  bash artifact/run.sh experiment "$1" --variant "$variant" --profile smoke
}
```

Equivalently, run `bash artifact/run.sh experiment NAME --variant baseline
--profile smoke` (or `--variant optimized`). Use `--profile paper` for the
diagnostic driver's larger workload. Its workload
is distinct from the uninstrumented throughput command; the recorded flags
identify the code/allocator change being visualized.

| Table 1 case | Before layout | After layout |
| --- | --- | --- |
| ASCYLIB/EFRB | `trace ascylib_efrb before` | `trace ascylib_efrb after` |
| ASCYLIB/DVY | `trace ascylib_dvy before` | `trace ascylib_dvy after` |
| ASCYLIB/HJ | `trace ascylib_hj before` | `trace ascylib_hj after` |
| TPC-C/BCCO | `trace tpcc_bcco before` | `trace tpcc_bcco after` |
| TPC-C/EFRB | `trace tpcc_efrb before` | `trace tpcc_efrb after` |
| RocksDB/HashSkipList | `trace rocksdb_hsl before` | `trace rocksdb_hsl after` |
| RocksDB/InlineSkipList | `trace rocksdb_isl before` | `trace rocksdb_isl after` |
| Valkey/string cache | `trace valkey_trace before` | `trace valkey_trace after` |
| HNSWLib | `trace hnsw_trace before` | `trace hnsw_trace after` |

Trace variant details:

- ASCYLIB/EFRB's after trace enables both segregation and parallel prefill.
- DVY compares 96-B and 192-B nodes. These traces inspect layout, not huge-page backing.
- TPC-C/BCCO's after trace combines segregation and the packed lock.
- TPC-C/EFRB uses mimalloc and a segregated tree on both sides; the after trace
  adds `MACROBENCH_SINGLE_RECMGR` and `MACROBENCH_PAD_ROW_TO_ALIGN`.
- HashSkipList applies the same field-order change in the upstream diagnostic snapshot.
- The supplied Valkey trace is also covered by the [walkthrough](GUIDED_WALKTHROUGH.md).

Valkey trace collection seals each persistent producer after the preload or
measured client phase ends, before shutting down the server. Shutdown activity
after sealing is outside the trace. Failed finalization or a failed server exit
prevents conversion. The logger also rejects failed/short asynchronous writes;
these are invalid traces, not successful partial results. This correctness fix
does not remove the cost of producing and writing allocation records.

To view a generated database, substitute the path printed by the trace command:

```bash
bash artifact/run.sh gui \
  --database artifact/results/ascylib_efrb-TIMESTAMP/ascylib_efrb.sqlite \
  --label efrb-before
```

Repeat with the optimized trace and a different label, such as `efrb-after`.
Each imported database remains in the GUI selector, so both can be revisited.
TPC-C databases use 2-MiB page mode; the other listed diagnostic drivers use
4-KiB page mode. Move the time slider into the populated interval. Inspect EFRB
cache-set usage, DVY node sizes/alignment, HJ allocation spacing, BCCO node/row
separation, EFRB retired-object accumulation over time, or HashSkipList bucket
field padding. Trace source snapshots and workloads are recorded separately
from the performance experiments; instrumentation itself can perturb layouts.

The commands in this section run the artifact's full-size performance
comparisons. See [Errata and updated reproduction configurations](#errata-and-updated-reproduction-configurations)
for differences from the submission and the corresponding measured results.
`--profile paper` selects the workload, allocator,
placement, and variants described below; no additional benchmark-specific
tuning flags or environment settings are needed beyond the commands shown.
Without `--profile paper`, commands default to small `smoke` workloads.
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

The section references use the submission's numbering.

The [reproduction configuration guide](REPRODUCTION_CONFIGURATIONS.md) expands
these defaults into explicit commands and gives confirmed improvements on the
named machines. Its extra flags spell out defaults, not additional tuning
required to reproduce those comparisons. Alternative configurations are labelled
separately; stored historical paper data are unchanged.

DVY's default `--dvy-hugepages auto` requests transparent huge pages for all four
layouts and records separate mapping checks before the timed runs. The driver
sets `GLIBC_TUNABLES=glibc.malloc.hugetlb=1` for each DVY benchmark process;
no manual runtime configuration is required. If backing is unavailable, it
warns and continues with the host's available pages. `--dvy-hugepages require`
instead stops before timing unless backing is observed for every layout;
`--dvy-hugepages off` disables allocator advice (not the host's THP policy).
Small smoke runs skip the full-size mapping checks. No host settings are changed.
Runtime versions, hashes and fallback warnings are in `runs/campaign.json`;
mapping evidence is in `runs/dvy-page-checks/`. A missing bundle in an older
image or native installation falls back to the installed runtime with a warning.

CPU IDs are discovered from the host topology and allowed CPU set. Paper
profiles retain their stated thread counts rather than silently downsizing:
use `--threads`, `--server-node`, and where applicable `--rocks-nodes` for a
different topology, or use smoke on a smaller machine. Retained allocator
libraries are included in the repository, not looked up in host-specific
installation paths. A missing or altered retained library requires restoring
the artifact files, not substituting another allocator into the comparison.

ASCYLIB and TPC-C build and save all variant binaries before measuring them.
Repetitions are interleaved, with one run of each variant per round and rotating
run order. RocksDB likewise builds both variants first and alternates their
order. `--trial-order blocked` instead runs all repetitions of each variant
together.

HNSW likewise builds separate variant modules before timing, then interleaves
fresh processes. Its paper profile runs both 128-D and 1536-D workloads, with
ten baseline/optimized pairs per dimension and alternating dimension/variant
order (40 trials total). Its factorization commands use the fixed orders in Section 4.

| Experiment | Variants compared |
|---|---|
| ASCYLIB EFRB | Baseline, object segregation, parallel prefill, both |
| ASCYLIB DVY | 96/72/128/192-byte node layouts |
| ASCYLIB HJ | glibc malloc / jemalloc backing the suballocator |
| TPC-C/BCCO | Baseline, node segregation, segregation + packed row lock |
| TPC-C/EFRB | Allocator, row-padding, and reclamation variants |
| RocksDB HashSkipList (`prefix_hash`) | Baseline / field reordering |
| RocksDB InlineSkipList (`skip_list`) | Baseline / alignment and separation of tall nodes |
| Valkey | Baseline / B1C1_64 small-object placement patch |
| HNSWLib | Packed layout / separate aligned vector slab + huge-page advice |

### Run all nine experiments

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh all-performance --profile paper
```

This runs the nine groups listed above sequentially, using the same standard
parameters as the individual paper-profile commands. Allow many hours and
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

HNSW uses 1M vectors at each of 128 and 1536 dimensions, 100k indexed queries,
24 build/query threads, M=16, ef_construction=200, ef=64, k=10, 10k warmup queries, and five timed
iterations. Allow hours for repeated fresh graph constructions. The output
includes QPS and `recall_mean`. The latter measures indexed queries finding
their own label; it is not ground-truth top-k ANN recall. `--dim N` selects a
single dimension; `--threads` changes both construction and query threads.
`hnsw` defaults to the existing corrected source snapshot, which issues
huge-page advice before first touch. `--hnsw-source original --dim 768`
selects the original implementation and workload. The smoke profile remains
a small 128-D check. The paper profile of `all-performance` also runs both dimensions.

Both RocksDB experiments use 10M initial keys, 32-byte keys, 128-byte values,
and disabled WAL/synchronous writes. They use different memtable configurations:

- HashSkipList uses 95 readers plus one writer, a 256-MiB write buffer, and a
  10-second read window after `filluniquerandom,waitforcompaction`. Flushing,
  automatic compaction, and shutdown flushing are enabled. The optimized
  variant enables only `REORDER_FIELDS=1`. The process uses 96 logical CPUs
  across two NUMA nodes, including SMT siblings, with memory interleaved across
  those nodes. `--rocks-nodes 0 1` selects the nodes (also the default).
  Each run retains its database, including SST files; allow tens of GiB of
  scratch storage for a full campaign.
- InlineSkipList uses 19 readers plus one writer and a 60-second read window,
  with alignment and segregation thresholds both set to 3. A 46.5-GiB write
  buffer keeps prefill and subsequent writes in memory. Automatic compaction
  and shutdown flushing are disabled, and there is no initial compaction wait.
  Every trial is checked for zero flush/compaction events, no SST/blob files,
  and no WAL payload, including at shutdown. Metadata and diagnostic writes
  remain. The paper profile requires at least 64 GiB available memory.

`--threads`, `--rocks-key-size`, and `--rocks-value-size` override the counts
and sizes. Both smoke profiles use two total threads, 10,000 initial keys,
and two-second measurements. Effective options and persistence checks are
saved with every run. See the [reproduction configurations](REPRODUCTION_CONFIGURATIONS.md#rocksdb-hashskiplist-field-reordering)
for the HashSkipList 7.51% and InlineSkipList 8.61% confirmations.

For ASCYLIB, TPC-C, InlineSkipList, and HNSW, paper-mode runs select one available hardware
thread per physical core on `--server-node` (default 0). Memory is bound to
that node except for standalone EFRB and DVY, which request single-node
interleaving to match their confirmed protocols. CPU IDs are discovered from the host's topology and allowed CPU set;
they are not assumed to match the paper's machine. `--threads N` changes the
worker count (readers plus writer for RocksDB; build/query threads for HNSW). `--cpus 0-7` or
`--cpus 0,2,4,6` explicitly selects that many distinct physical cores on the
chosen node. TPC-C pins individual workers; ASCYLIB, RocksDB and HNSW run within the
selected CPU set. `--memory-policy interleave` selects single-node interleaving
instead of strict binding. HashSkipList is the exception: its CPU selection
uses equal logical CPU counts on `--rocks-nodes`, including SMT, and defaults
to two-node interleaving; `--cpus` can supply an explicit balanced mask.
Small smoke runs omit NUMA placement unless `--cpus`, `--memory-policy`, or
`--rocks-nodes` is supplied.

ASCYLIB also accepts `--initial`, `--range`, `--duration-ms`, and `--update-pct`.
Use these command-line options rather than outer-shell `THREADS=...` or
`INITIAL=...` assignments: the options pass through the Docker wrapper.
For example, run the default four-thread EFRB configuration explicitly:

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_efrb_bench \
  --profile paper --threads 4 --initial 262144 --range 524288 \
  --duration-ms 5000 --reps 10 --server-node 0 --memory-policy interleave
```

ASCYLIB rounds non-power-of-two initial sizes upward. EFRB defaults to four
threads, 262,144 initial keys, and 5,000 ms. DVY defaults to eight threads and
HJ to 24; both use 1,048,576 initial keys and 5,000 ms. `all-performance` uses
these same defaults. All three default to
search-only workloads; the default key range is twice the rounded initial size.
EFRB's earlier eight-thread comparison is available with
`--threads 8 --memory-policy bind`; HJ's earlier setting with `--threads 8`.

Both TPC-C commands use 24 workers and 24 warehouses, the full schema,
50% Payment/50% NewOrder transactions, and no warmup transactions. They use
the benchmark's transaction-count stopping rule (`MAX_TXN_PER_PART=100000`),
not a fixed-duration window. Throughput is calculated from the actual committed
transactions and elapsed time reported by each run.

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
Both RocksDB configurations use the retained process-wide jemalloc 5.3 library.
Its path and checksum are recorded in `protocol.json`
and each trial's `config.json`.
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
Both attribution commands retain their 768-D default; add `--dim 128` or
`--dim 1536` to attribute the effects at either headline workload dimension.

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
The two-dimension HNSW run records separate configurations and dimension-labelled
trial files; `summary.json` reports each dimension under `by_dimension`, without
pooling their throughputs.

ASCYLIB and TPC-C runs write `results.tsv`, `summary.txt`, and per-run logs
under `artifact/results/<name>-<UTC timestamp>/`. `protocol.json` records the selected
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

Every `artifact/run.sh experiment NAME` invocation creates a fresh timestamped
directory, including its builds, raw logs, and summaries. Rerun the same command
without another checkout. All processing steps receive that invocation's exact
directory; they do not search for the newest result. `--out` selects a specific
new directory. Named experiments from one checkout must run sequentially because
instrumentation tools have shared build products. Older results under
`artifact/experiments/` are left untouched.

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

### Sampling and objects that cross pages

The native converter samples memory pages with probability `p` (the `--sample`
option), then adds pages as needed to meet the per-type minimum `s`
(`--pages-per-type`). Allocations crossing page boundaries produce a record for
each page-local fragment, with the original allocation address retained.
Selecting a page does not force selection of neighbouring fragments, and there
is no recursive expansion through overlapping objects. With `p=1`, all pages
are retained intentionally. Per-type minima and explicitly perf-directed pages
can also increase the selected set; these are not a fixed total-page budget.

The GUI subsequently clusters retained pages and selects representatives.
That display selection is separate from native trace-to-database sampling.
This camera-ready branch defaults to 128 representative pages and 100,000
prepared history records. After retaining mandatory perf-directed pages, it
tries to represent each cluster, then cover missing types, then include
history-size extremes and additional page runs within both budgets. The UI
reports omitted clusters/types and mandatory-perf budget exceptions. Neighbouring
pages are not forced into the display. The evaluator-facing `main` branch
retains its earlier selector and 52/17-page defaults.

The converter's `s` is a database-retention floor of `min(s, available pages)`
per type, not a GUI representative count. It is applied before clustering;
the GUI's missing-type pass tries to include one page for each still-unrepresented
type within its budgets and does not use `s`. Likewise, `p` is the random
retention probability before the per-type/perf additions, not a page's final
probability of appearing in the GUI. With `p=1`, the per-type floor has no
additional effect. Direct backend callers and the CLI exporter must explicitly
pass page/record budgets to use the GUI's new defaults.

New databases retain each allocation's original address and size, so zigzag
marks distinguish continuation across a page boundary from a true object end.
Older databases remain readable but omit continuation marks when the original
extent is unknown. Ordinary object boundaries retain their solid outlines.

### Generate and open a trace

For `experiment NAME`, names without `_bench` generate instrumented allocation
traces for the GUI.
For example, to generate a small EFRB trace:

```bash
bash artifact/run.sh experiment ascylib_efrb --profile smoke
```

The trace-generation names are `ascylib_efrb`, `ascylib_dvy`, `ascylib_hj`,
`tpcc_bcco`, `tpcc_efrb`, `rocksdb_hsl`, `rocksdb_isl`, `valkey_trace`, and `hnsw_trace`. Their generated SQLite databases
are written under `artifact/results/<name>-<UTC timestamp>/`. Trace generation is
separate from the uninstrumented performance experiments above.

InlineSkipList traces include explicit annotations for the regions carved from
its arenas: each node and its key, and the upper-level pointer array immediately
before it. These annotations leave allocation unchanged. In the optimized
variant, arrays belonging to nodes taller than three levels are 64-byte aligned
and allocated in a separate arena. Inspect the `InlineSkipList` node and
`std::atomic<...Node*>` types; the driver checks their presence and the sampled
tall-array alignment. The database is `rocksdb_isl.sqlite`.

Valkey traces use bundled jemalloc and preload 2,000 keys in smoke mode or one
million in the larger diagnostic profile, with 128-byte values. Each variant
produces `valkey.sqlite`. Compare the `robj` placement before and after the
patch; this SET preload is for layout inspection, not the concurrent throughput
measurement. The optimized instrumentation calls the patched allocators.

If opening a trace exceeds the cache-view memory budget, use the error's
**Retry with fewer time buckets** link. This reduces temporal resolution only
when requested; it does not change cache geometry. Once loaded, the time-bucket
setting is also available in Settings.

HNSWLib traces use the performance source snapshot with semantic annotations for
slabs, elements, vector payloads, links, and labels. The smoke profile builds
2,000 vectors at 128 dimensions; the larger diagnostic profile builds one million
vectors at each of 128 and 1536 dimensions (`--dim` selects one).
Databases are saved as `d128/hnsw.sqlite` and `d1536/hnsw.sqlite` within the result
directory. Compare the packed vectors with the separate, 64-byte-aligned vector
slab. Nested regions are reconstructed using the converter's `--use-container`
option, which this driver supplies automatically.

For a guided Valkey LLM example, follow [LLM_EXAMPLE.md](LLM_EXAMPLE.md).
It includes the saved input and optimization patch, plus prompts for a
fresh model-assisted run. To regenerate the text input from the supplied trace:

```bash
bash artifact/run.sh export
```

The GUI also offers **Export 5 snapshots** above its page pane for the currently
selected representative pages. This is an on-demand export with progress and
cancellation, separate from the command-line LLM export above. See the root
[README](../README.md#representative-pages-and-text-export) for export options
and the GUI's page/history budgets.

## 7. Reproduce logging overhead (C2)

This command measures baseline versus instrumented execution using the stock
HeapLENS logger. It builds matched ASCYLIB EFRB, DVY, and BCCO binaries and runs
20% and 100% update workloads, alternating baseline/logging order between
repetitions. The BCCO workload here is the standalone tree, not TPC-C/BCCO.

```bash
# Small end-to-end check of the measurement and trace capture.
bash artifact/run.sh overhead --profile smoke --overhead-trees efrb

# Full C2 configuration, ten repetitions of each variant/workload.
HEAPLENS_NUMA=1 bash artifact/run.sh overhead --profile paper
```

Paper mode uses 24 physical cores on `--server-node` (default 0), single-node
memory interleaving, 10,000,000 requested initial keys (rounded by ASCYLIB to
16,777,216), and a 3,000-ms measured phase. Both builds use `INIT=all`,
`SET_CPU=0`, and `VERSION=O3`; logging additionally uses HeapLENS's source
instrumentation and logger. Both use the same dynamic SSMEM allocator.
The build/runtime protocol follows the retained overhead experiment, not the
search-only optimization workloads in Section 3.

`--threads`, `--cpus`, `--server-node`, `--initial`, `--duration-ms`, `--update-pct`,
`--reps`, and `--overhead-trees efrb dvy bcco` allow smaller or targeted runs.
For example, append `--threads 6` on a six-core host; report that configuration
with its result. Smoke mode uses two workers (or the available smaller count),
4,096 initial keys, 1,000 ms, and one repetition per variant/update rate.

Results are saved in `artifact/results/overhead-<timestamp>/`: `protocol.json`,
build logs and binaries, per-trial commands, raw benchmark output, compressed
allocation logs, `results.json`, and `summary.json`. The reported overhead is
`100 * (1 - mean(logging throughput) / mean(baseline throughput))`. Compression
and verification occur after timing. Only a newly generated raw log is removed,
after its compressed copy has been independently hash-verified.

Allow at least 100 GiB of free disk space for paper-mode builds and traces.
The runner stops before starting a trial if fewer than 50 GiB remain; individual
paper logs are capped at 20 GiB and trials at 900 seconds. Storage speed can
affect logging overhead, so report the trace-output device. This command does
not enable the separate diagnostic buffer-wait probe or count I/O waits.

### Measured logging overhead

The packaged full campaign completed all 120 trials on the dual Xeon Gold
5220R machine using the configuration above: ten repetitions of each
baseline/logging variant at each update rate for each tree. The measured
reductions in mean throughput were:

| Workload | 20% updates | 100% updates |
|---|---:|---:|
| EFRB | 3.30% | 10.66% |
| DVY | 0.17% | 5.38% |
| BCCO | -2.02% | 1.21% |

The negative BCCO value means the instrumented runs were slightly faster in
this campaign; we do not interpret it as a benefit of logging. These are
measurements from the packaged reproduction, separate from the historical
overhead results in `paper_data.xlsx`.

## Errata and updated reproduction configurations

Paper section, appendix, and Table 1 references in this README refer to the
submission. The corrections and configuration updates below will be reflected
in the camera-ready paper. The supplied workbook and `artifact/historical/`
preserve the submission's underlying measurements.

### Paper corrections

**Counter normalization.** The original ASCYLIB (EFRB, DVY, HJ) and TPC-C
(BCCO, EFRB) scripts inadvertently divided cache/TLB miss and context-switch
counts by throughput rather than operation/transaction counts. This artifact
uses the actual counts and retains the raw counters. Corrected per-operation
values therefore differ from those in the paper. Throughput measurements and
speedups are unaffected. Relative counter changes are preserved when measurement
durations match, apart from rounding; they require recalculation for
variable-duration TPC-C runs. The supplied workbook preserves the original data.

**Valkey improvement.** The submission inconsistently reports the historical
maximum improvement as 5.9% and 6.2%; 5.9% is correct. The artifact's ten-pair
reproduction measured a mean improvement of 4.45%, compared with the historical
mean of 4.23%.

### Changed experimental configurations and corresponding results

During artifact validation, we clarified several incompletely specified
settings and measured some comparisons under revised configurations. We
distinguish these below. The README's `--profile paper` commands use the
configurations listed here; their measured throughputs and improvements are
the reference results for those commands. We will update the camera-ready
paper's configurations and results together.

The following comparisons use changed settings or implementation details.
All updated measurements below were collected on the dual Xeon Gold 5220R
machine. Throughputs are means, and updated percentage gains are ratios of
mean throughput.

| Experiment | Configuration change | Submission's improvement | Updated before throughput | Updated after throughput | Updated improvement |
|---|---|---:|---:|---:|---:|
| Standalone EFRB | Five-second trials, matching the submission's description; the retained script specifies three seconds | 35.14% | 6,755,200 ops/s | 8,755,900 ops/s | 29.62% |
| HJ | 24 threads instead of eight | Approximately 4% | 35,622,600 ops/s | 37,567,200 ops/s | 5.46% |
| HNSWLib, 128-D | 128 dimensions instead of 768; corrected huge-page advice placement, described below | 6.3% mean; 16% maximum at 768-D | 66,340.30 queries/s | 72,650.18 queries/s | 9.51% |
| HNSWLib, 1536-D | 1536 dimensions instead of 768; corrected huge-page advice placement, described below | 6.3% mean; 16% maximum at 768-D | 7,156.33 queries/s | 7,626.05 queries/s | 6.56% |
| RocksDB InlineSkipList | Memory-only workload on 20 physical cores, without the compaction wait described in the submission | Approximately 3% | 5,810,938.5 ops/s | 6,311,177.9 ops/s | 8.61% |

**HNSWLib:** The artifact uses a corrected implementation that issues
vector-slab huge-page advice before first touch. The submission's 6.3% is
the mean of individual relative gains; its retained measurements give 6.17%
using the ratio-of-means statistic used above. The original source and
768-dimensional workload remain available through
`--hnsw-source original --dim 768`.

**InlineSkipList:** The memory-only configuration disables WAL, automatic
compaction, and shutdown flushing, and provides sufficient memtable capacity
to avoid SST writes.

[Reproduction configurations](REPRODUCTION_CONFIGURATIONS.md) provides complete
commands, settings, and confidence intervals. Results from changed
configurations are reported separately from historical measurements.
The HNSWLib factorization commands in Section 4 additionally separate the
effects of layout changes and huge-page advice, and of separation and alignment.
These analyses supplement the submitted evaluation.

### Clarified or previously unspecified settings

These entries document settings separately from the changes above. Where
historical evidence establishes a setting, we identify it; where the artifact
makes an environmental dependency explicit, we describe that control.

| Experiment | Clarification |
|---|---|
| Standalone EFRB | The retained data behind the reported gain use four threads; the artifact selects four threads. |
| DVY | Explicitly control and check huge-page backing, applying the same allocator advice policy to every node-layout variant. The artifact supplies an isolated runtime for this purpose. |
| RocksDB HashSkipList | Specify the retained workbook's 96-thread, 10-million-key, 32/128-byte key/value, 256-MiB-buffer configuration. WAL is disabled, but flushing and compaction remain enabled. |

### Optional PMU and logging-overhead evidence

[Retained 400-cell results and analysis](headline-pmu/README.md) are separate
from ordinary throughput reproduction. Recomputing their summaries is quick;
full measurement reproduction requires explicit opt-in, **48 hours or more**,
and substantial storage (observed archives alone: **254.2 GiB**). The linked
guide explains provisioning, logger-version differences, and current workflow
limits. These measurements must not be silently attributed to a newer logger.

The HNSW diagnostic trace includes query-context `new`/`new[]` allocations as
`HeapLensHnswQueryScratch`, in addition to semantic index regions. This label
describes allocations within `searchKnn`, not exact STL types or exhaustive
Python/NumPy coverage. It preserves the original allocator and layout behavior.

### Artifact packaging correction

**TPC-C allocator separation.** The initial artifact inadvertently pointed the
tree-segregation allocation path at the process-wide jemalloc library. Loading
that same library again did not provide the second segregating allocator it
was supposed to. The corrected drivers restore the distinct jemalloc library
used by the retained experiments and reject accidental reuse of the global
allocator. This was introduced during artifact preparation; the retained paper
results are unchanged. See
[allocator provenance](vendor/heaplens-allocators/README.md).
