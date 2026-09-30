# Reproduction configurations

These are the standard paper-profile configurations selected by the main
README's commands and `all-performance --profile paper`. Flags written out
in the primary recipes make the defaults explicit; they are not extra tuning
steps. Alternative workloads and factorization commands are labelled separately.
Repetition counts are stated below (ten per variant unless specified).
Run from the repository root after building the Docker image.
Commands create a new timestamped directory under `artifact/results/` for each
invocation, so repeated campaigns do not require a fresh checkout.

## Standalone EFRB: four threads

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_efrb_bench \
  --profile paper --threads 4 --initial 262144 --range 524288 \
  --duration-ms 5000 --update-pct 0 --reps 10 \
  --server-node 0 --memory-policy interleave
```

This default uses four physical cores on one socket, glibc backing, and the four
existing baseline/segregation/parallel-prefill/combined variants. On the
dual Xeon Gold 5220R machine, ten repetitions per variant gave a combined
gain of 29.62% (95% interval 28.45–31.13%); segregation alone gave 19.76%
and parallel prefill 21.83%. A separate duration comparison confirmed
29.82% at five seconds and 29.69% at ten seconds. Those batches are not pooled.
The historical four-thread result is 35.14%; the remaining gap is not erased
by this configuration correction. The retained script uses three-second
windows, whereas the paper describes five seconds; the default uses five.

The earlier eight-thread, five-second, strictly bound comparison remains
available with `--threads 8 --memory-policy bind`. It gave 27.24%
(26.61–27.89%), versus the historical eight-thread 25.38% result. Diagnostic
trace and instrumentation-overhead thread counts are separate experiments.

## DVY: equal huge-page advice for all node layouts

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_dvy_bench \
  --profile paper --threads 8 --initial 1048576 --range 2097152 \
  --duration-ms 5000 --update-pct 0 --reps 10 \
  --server-node 0 --memory-policy interleave
```

The default requests transparent huge pages for **every** layout using a
corrected libc bundled in the Docker image, without upgrading the host or
changing any other benchmark's runtime. Both baseline and optimized nodes use
the same allocator/advice policy. Four separate full-workload diagnostic
processes record `smaps`; the following timing processes are unprobed.

`--dvy-hugepages require` makes the page-backing check mandatory. The default
`auto` warns and continues if the host cannot supply huge pages, or if an older
image lacks the runtime bundle. `--dvy-hugepages off` compares layouts with
allocator advice off under the same selected runtime; global THP `always`
can still supply huge pages. Runtime selection, versions and library hashes
are recorded in `runs/campaign.json`, and the backing check in
`runs/dvy-page-checks/summary.json`. Rebuild the image to obtain the supplied
runtime; no exact libc/compiler package version is required on the host.

On Pyke (dual Xeon Gold 5220R), this command's default configuration gave
17,467,000 ops/s for 96-B nodes and 20,683,600 ops/s for 192-B nodes:
**18.42%** improvement (paired-block bootstrap 95% interval **17.14–19.82%**),
compared with the historical 17.54%. All 40 trials were retained. These were
source builds using the artifact's GCC 11.4/O2, non-PIE and static SSMEM,
with the isolated libc 2.39 runtime. Separate mapping checks observed huge-page
backing for all four layouts. Hardware/kernel differences can change the gain.

## HJ: allocator comparison at 24 threads

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_hj_bench \
  --profile paper --threads 24 --initial 1048576 --range 2097152 \
  --duration-ms 5000 --update-pct 0 --reps 10 --hj-jemalloc 5.3 \
  --server-node 0 --memory-policy bind
```

This compares glibc against retained jemalloc 5.3.0 with otherwise identical
settings. The dual Xeon Gold 5220R result was 5.46% higher mean throughput with
glibc (95% interval 2.19–9.02%). Variation is substantial: individual paired
changes ranged from -0.70% to +13.89%; all runs were retained. The default worker
count is 24, so the command without overrides and `all-performance` use this
configuration. The comparison defaults to jemalloc 5.3;
`--hj-jemalloc 5.0` preserves access to the initial artifact's jemalloc 5.0.1.
Allocator paths and hashes are recorded in `runs/campaign.json`.

## HNSW: dimension and huge-page placement

The 128-D and 1536-D before/after comparisons were confirmed on both the
dual Xeon Gold 5220R machine (kernel 6.8.0-137-generic) and a four-socket Xeon
Platinum 8160 machine (kernel 5.8.0-55-generic). Each uses 24 physical cores
and memory from one NUMA node, system libc, one million vectors,
100,000 indexed queries, 24 construction/query threads, M=16, ef_construction=200,
ef=64, k=10, 10,000 warmup queries, and five timed iterations (500,000 queries).

Run both dimensions with the default paper command:

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw --profile paper
```

The corrected snapshot is already part of the artifact. Its vector-slab
huge-page advice precedes first touch. Both variants use that same snapshot,
with the layout/huge-page macros disabled for baseline. Ten blocks each contain
baseline and combined trials at both dimensions (40 processes total), alternating
dimension and variant order. Results remain separate by dimension. Add
`--dim 128` or `--dim 1536` to run just one. The original snapshot and 768-D
workload remain accessible with `--hnsw-source original --dim 768`.

| Dimension | Xeon Gold 5220R combined gain | 95% interval | Xeon Platinum 8160 combined gain | 95% interval |
|---:|---:|---:|---:|---:|
| 128 | +9.51% | 9.41–9.59% | +7.15% | 7.03–7.25% |
| 1536 | +6.56% | 6.44–6.68% | +6.17% | 6.05–6.29% |

All ten before/after pairs were positive at each dimension on both machines.
On the Xeon Gold 5220R, mean baseline/combined QPS were 66,340/72,650 at 128D
and 7,156/7,626 at 1536D, with within-variant coefficients of variation below 0.16%.

To measure all four combinations of layout changes and huge-page advice:

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw-factorization --factors hugepage \
  --profile paper --dim 128 --threads 24 --reps 10 --server-node 0 --memory-policy bind

HEAPLENS_NUMA=1 bash artifact/run.sh hnsw-factorization --factors hugepage \
  --profile paper --dim 1536 --threads 24 --reps 10 --server-node 0 --memory-policy bind
```

The four-variant factor analysis below was measured on the Xeon Platinum 8160;
it does not decompose the Xeon Gold 5220R gains.

| Dimension | Layout alone | Huge pages alone | Combined | Combined 95% interval |
|---:|---:|---:|---:|---:|
| 128 | +0.73% | +2.35% | +7.15% | 7.03–7.25% |
| 1536 | +1.97% | +2.10% | +6.17% | 6.05–6.29% |

Layout here groups vector separation and 64-byte alignment. Separate mapping
diagnostics found more than 99.9% huge-page backing for the combined variant's
vector slabs and zero for baseline/layout-only index allocations. The timing
processes themselves were uninstrumented. These dimension-specific gains do
not establish the same gain at 768 dimensions: the Xeon Platinum 8160's fixed 768-D
comparison gave 1.87%. Multithreaded graph construction is nondeterministic.

## RocksDB HashSkipList: field reordering

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh rocksdb --memtable prefix_hash --profile paper
```

The default uses 96 logical CPUs across NUMA nodes 0 and 1, including SMT,
with memory interleaved across the two nodes. There are 95 readers plus one
writer, 10M initial keys, 32-byte keys, 128-byte values, a 256-MiB write buffer,
and a 10-second read window after `filluniquerandom,waitforcompaction`.
WAL and synchronous writes are disabled; ordinary flushing, automatic
compaction, and shutdown flushing are enabled. The retained jemalloc 5.3
library and release/portable build are identical between variants; only the
existing `REORDER_FIELDS=1` option differs. `NO_PADDING_NODE` is not enabled.

`--rocks-nodes 2 3` selects another pair of NUMA nodes. CPU IDs are discovered
from the topology and allowed CPU set; `--threads` selects an even total count
distributed equally across the two nodes. Placement constrains the process's
CPU set, rather than pinning individual workers. Full runs save their SST files
and require tens of GiB of scratch storage.

On the dual Xeon Gold 5220R, five interleaved before/after pairs gave mean
read throughput of 14,658,378.2 / 15,759,045.6 operations/s: **+7.51%**, with
a paired-block 95% interval of **5.72–9.34%**. A separate ten-pair batch with
the same binaries and workload gave +5.17% (2.37–7.82%); the batches are not
pooled. The historical workbook's ten trials per variant give +8.28%
(6,223,092.0 / 6,738,584.1 operations/s). Thus the relative gain is comparable,
while absolute throughput differs. The artifact command defaults to ten
interleaved repetitions per variant.

The workload's 96-thread, 10M-key, 32/128-byte, 256-MiB settings and field-reordering
comparison match the historical workbook labels. The complete historical build
and launch command have not been recovered; the command above uses the verified
release-build configuration. The driver records commands, effective options,
allocator/binary checksums, and checks disabled WAL and the memtable settings
for every trial. Historical measurements remain unchanged.

## RocksDB inline skiplist: memory-only

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh rocksdb --memtable skip_list --profile paper
```

This default selects 20 physical cores and memory from NUMA node 0, 19 readers
plus one writer, 10M initial keys, 32-byte keys, 128-byte values, 60-second
read windows, retained jemalloc 5.3, and ten interleaved repetitions per
variant. `--threads` and `--server-node` select another core count or node.
Both variants use the same source snapshot; the modified binary enables the
existing `ALIGN_TALL_NODE=3 SEG_TALL_NODE=3` implementation.

The memtable has a 46.5-GiB write buffer, with WAL, automatic compaction, and
shutdown flushing disabled. There is no initial compaction wait. These
settings keep user data in the memtable throughout prefill, measurement, and
shutdown; the driver verifies this in every trial. Metadata and diagnostic
log writes remain. Full runs require at least 64 GiB available memory.

On the dual Xeon Gold 5220R machine, baseline/modified mean read throughput
was 5,810,938.5 / 6,311,177.9 operations/s: **+8.61%**, with a paired-block
95% interval of **8.32–8.92%**. Each variant's throughput CV was below 0.31%.
The confirmation retained all ten pairs and separately passed six small
smokes and three full-size baseline preflights across the tested topologies.

The same 20 software threads on ten physical cores with SMT gave +9.09%
(8.41–9.79%). That is a topology comparison, not a worker-count sweep;
the default artifact command uses the 20-physical-core configuration above.
The memory-only workload differs from a small-buffer run that flushes data
to SSTs; do not pool the two configurations.

`rocksdb-options.ini` and `protocol.json` capture the requested configuration.
Each trial saves its command, allocator checksum, effective RocksDB options,
DB log, and `persistence.json` verification. If a custom workload exhausts
the buffer and causes data flushing, the driver fails the check instead of
reporting it as a memory-only result. These persistence controls are specific
to InlineSkipList; HashSkipList uses the 256-MiB configuration above.

## Reading these comparisons

The measurements above are fresh confirmations after a configuration screen,
not pooled with that screen. Gains are ratios of mean throughput. The intervals
are paired-block bootstrap intervals describing within-session variability.
Raw historical paper measurements remain under `artifact/historical/` and in
the workbook; they have not been relabelled with these configurations.

Except for HashSkipList's two-node SMT configuration, the commands select
physical cores from the actual topology. Memory is bound locally except for
standalone EFRB and DVY's single-node interleaving.
All HNSW modules build before timing; separate processes use
the saved modules in interleaved order. `protocol.json`, source and binary
manifests, per-block commands/logs/CSVs and `summary.json` record the run.
`summary.json` uses ratios of means; the additional factorization reports also
include paired-effect statistics, explicitly labelled by their summaries.
