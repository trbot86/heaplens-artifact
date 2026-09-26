# Reproduction configurations

These recipes expose configurations confirmed with ten fresh repetitions per
variant. Run from the repository root after building the Docker image.
Use a fresh checkout for each ASCYLIB campaign, as described in the main README.
HNSW automatically creates a new output directory for each command.

## Standalone EFRB: eight threads

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_efrb_bench \
  --profile paper --threads 8 --initial 262144 --range 524288 \
  --duration-ms 5000 --update-pct 0 --reps 10 \
  --server-node 0 --memory-policy bind
```

This uses eight physical cores on one socket, glibc backing, and the four
existing baseline/segregation/parallel-prefill/combined variants. On the
dual Xeon Gold 5220R machine, the combined gain was 27.24% (95% interval
26.61–27.89%); segregation alone gave 20.05% and parallel prefill 19.04%.
The unchanged default remains 24 threads; this command explicitly selects eight.

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
count remains eight. The comparison now defaults to jemalloc 5.3;
`--hj-jemalloc 5.0` preserves access to the initial artifact's jemalloc 5.0.1.
Allocator paths and hashes are recorded in `runs/campaign.json`.

## HNSW: dimension and huge-page placement

The 128-D and 1536-D confirmations used 24 physical cores on one NUMA node of
a four-socket Xeon Platinum 8160 machine (host kernel 5.8.0-55-generic), rather
than the dual Xeon Gold 5220R machine. They used system libc, one million vectors,
100,000 indexed queries, 24 construction/query threads, M=16, ef_construction=200,
ef=64, k=10, 10,000 warmup queries, and five timed iterations (500,000 queries).

Run the before/after comparison at either dimension:

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw --profile paper \
  --hnsw-source corrected --dim 128 --threads 24 --reps 10 \
  --server-node 0 --memory-policy bind

HEAPLENS_NUMA=1 bash artifact/run.sh hnsw --profile paper \
  --hnsw-source corrected --dim 1536 --threads 24 --reps 10 \
  --server-node 0 --memory-policy bind
```

The corrected snapshot is already part of the artifact. Its vector-slab
huge-page advice precedes first touch. Both variants use that same snapshot,
with the layout/huge-page macros disabled for baseline. The default `hnsw`
command still selects the original source and 768 dimensions.

To measure all four combinations of layout changes and huge-page advice:

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw-factorization --factors hugepage \
  --profile paper --dim 128 --threads 24 --reps 10 --server-node 0 --memory-policy bind

HEAPLENS_NUMA=1 bash artifact/run.sh hnsw-factorization --factors hugepage \
  --profile paper --dim 1536 --threads 24 --reps 10 --server-node 0 --memory-policy bind
```

| Dimension | Layout alone | Huge pages alone | Combined | Combined 95% interval |
|---:|---:|---:|---:|---:|
| 128 | +0.73% | +2.35% | +7.15% | 7.03–7.25% |
| 1536 | +1.97% | +2.10% | +6.17% | 6.05–6.29% |

Layout here groups vector separation and 64-byte alignment. Separate mapping
diagnostics found more than 99.9% huge-page backing for the combined variant's
vector slabs and zero for baseline/layout-only index allocations. The timing
processes themselves were uninstrumented. These dimension-specific gains do
not establish the same gain at 768 dimensions: that machine's fixed 768-D
comparison gave 1.87%. Multithreaded graph construction is nondeterministic.

## Reading these comparisons

The measurements above are fresh confirmations after a configuration screen,
not pooled with that screen. Gains are ratios of mean throughput. The intervals
are paired-block bootstrap intervals describing within-session variability.
Raw historical paper measurements remain under `artifact/historical/` and in
the workbook; they have not been relabelled with these configurations.

The commands select physical cores from the actual machine topology and bind
memory locally. All HNSW modules build before timing; separate processes use
the saved modules in interleaved order. `protocol.json`, source and binary
manifests, per-block commands/logs/CSVs and `summary.json` record the run.
`summary.json` uses ratios of means; the additional factorization reports also
include paired-effect statistics, explicitly labelled by their summaries.
