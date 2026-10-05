# HeapLENS — ACM ATC 2026 artifact

**Paper:** *HeapLENS: Heap Layout Evaluation & Navigation Suite*, paper 483.
This guide follows the submitted paper's Table 1 and main figures. Each result
below has a complete command, an output location and an expected observation.
The [full configuration and reference guide](REPRODUCTION_CONFIGURATIONS.md)
contains workload parameters, NUMA placement, allocators, variants, sampling,
appendix figures, result schemas and errata. Those details are reference material;
the commands here already select the documented defaults.

## 1. Install and check the artifact

Use an x86-64 Linux shell with Docker Engine, from the repository root.
Budget about 20 GB disk and 8–16 GB RAM for installation and small checks.
Full experiments take many hours and need more resources: in particular,
HashSkipList needs 96 logical CPUs across two nodes; InlineSkipList needs
64 GiB available memory; Valkey needs 24 physical cores on each of two nodes.
See [requirements and runtimes](REPRODUCTION_CONFIGURATIONS.md#requirements-and-runtimes).

For a Git checkout, first initialize the pinned dependencies (the source archive
already includes them):

```bash
git submodule update --init artifact/vendor/ascylib artifact/vendor/setbench artifact/vendor/rocksdb
git -C artifact/vendor/setbench submodule update --init common/recordmgr tools
```

```bash
bash artifact/run.sh build
bash artifact/run.sh smoke
```

The first build needs Internet access. The smoke check normally takes under a
minute after building. Expect `Python imports OK`, ten saved runs per
Valkey/HNSW variant, `Export OK`, and a new `artifact/results/smoke-<timestamp>/`
directory. This checks saved data and export functionality; it is not a new
performance measurement.

All result paths below are **host paths relative to the repository root**.
The same root is mounted at `/root/sifter` in the container; that prefix can
still appear in raw command logs. The runner prints the corresponding absolute
host result path. `--out artifact/results/NEW_NAME` chooses a new directory;
existing directories are never overwritten. Use a different name when repeating
a figure command. Run named experiments sequentially in a checkout.

## 2. Inspect a saved trace

```bash
bash artifact/run.sh gui
```

Open <http://localhost:3000>, choose `valkey-artifact.sqlite`, and follow the
[guided walkthrough](GUIDED_WALKTHROUGH.md). Move the timeline into a populated
interval. The small `efrb-smoke.sqlite` trace is also supplied. Ctrl-C stops the
servers. [Remote access and small benchmark checks](REPRODUCTION_CONFIGURATIONS.md#gui-and-small-benchmark-checks)
are optional.

## 3. Reproduce Table 1 performance comparisons

Each command builds all its variants and uses ten repetitions per variant.
Expect machine-dependent variation, not exact equality. The references below
are the evaluator configuration confirmations documented in the linked guide;
TPC-C entries explicitly retain the submission's approximate targets. They are
not pooled with the separate camera-ready campaign. Gains are ratios of mean
throughput, `100 * (after / before - 1)`.

ASCYLIB/TPC-C counter commands require a Docker host kernel >=5.8, `PERFMON`
support and permitted PMU access. For throughput alone, replace
`HEAPLENS_PERF=1` with `PERFBENCH_PERF=off`. No host policies are changed.
Counter normalization and whole-process scope are explained in the
[result schema](REPRODUCTION_CONFIGURATIONS.md#find-and-interpret-results).

### ASCYLIB/EFRB

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_efrb_bench --profile paper
```

Output: `artifact/results/ascylib_efrb_bench-<timestamp>/summary.txt`, comparison
`d_both / a_default`. Expected: about **+29.62%**, using four threads and both
parallel prefill and object segregation. [Full configuration](REPRODUCTION_CONFIGURATIONS.md#standalone-efrb-four-threads).

### ASCYLIB/DVY

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_dvy_bench --profile paper
```

Output: `artifact/results/ascylib_dvy_bench-<timestamp>/summary.txt`, compare
`d_192B_pad / a_96B_default`. Expected: about **+18.42%** with equal huge-page
advice and observed backing; check `runs/dvy-page-checks/summary.json`.
[Full configuration and fallback behavior](REPRODUCTION_CONFIGURATIONS.md#dvy-equal-huge-page-advice-for-all-node-layouts).

### ASCYLIB/HJ

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_hj_bench --profile paper
```

Output: `artifact/results/ascylib_hj_bench-<timestamp>/summary.txt`, compare
`glibc_malloc / jemalloc`. Expected: about **+5.46%**, with substantial variation,
at 24 threads. [Full configuration](REPRODUCTION_CONFIGURATIONS.md#hj-allocator-comparison-at-24-threads).

### TPC-C/BCCO

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment tpcc_bcco_bench --profile paper
```

Output: `artifact/results/tpcc_bcco_bench-<timestamp>/summary.txt`, comparison
`c_seg_ds_pack_lock / a_default`. Expected: roughly **+16%**, the submission's
Table 1 target for segregation plus packed locks.
[Workload and allocator details](REPRODUCTION_CONFIGURATIONS.md#hardware-and-workloads).

### TPC-C/EFRB

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment tpcc_efrb_bench --profile paper
```

Output: `artifact/results/tpcc_efrb_bench-<timestamp>/summary.txt`, comparison
`e_single_recmgr_mimalloc_fixed / b_mimalloc`. Expected: roughly **+20%**, the
submission's Table 1 target. This combines shared reclamation and padded rows,
holding mimalloc and tree segregation fixed.
[Comparison definitions](REPRODUCTION_CONFIGURATIONS.md#hardware-and-workloads).

### RocksDB/HashSkipList

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh rocksdb --memtable prefix_hash --profile paper
```

Output: `artifact/results/rocksdb-<timestamp>/summary.json`,
`variants.optimized.change_percent_vs_baseline`. Expected: about **+7.51%** in
the documented five-pair confirmation, using the native rate. New runs also
record reader-only rates and writer completion times; those are distinct metrics.
[Full configuration and timing definitions](REPRODUCTION_CONFIGURATIONS.md#rocksdb-hashskiplist-field-reordering).

### RocksDB/InlineSkipList

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh rocksdb --memtable skip_list --profile paper
```

Output: `artifact/results/rocksdb-<timestamp>/summary.json`,
`variants.optimized.change_percent_vs_baseline`. Expected: about **+8.61%** for
the memory-only configuration; every trial must pass its persistence check.
[Full configuration](REPRODUCTION_CONFIGURATIONS.md#rocksdb-inline-skiplist-memory-only).

### Valkey/string cache

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh valkey --profile paper
```

Output: `artifact/results/valkey-<timestamp>/summary.json`,
`variants.B1C1_64.change_percent_vs_baseline`. Expected: about **+4.45%** mean
in the evaluator confirmation (historical mean +4.23%, maximum +5.9%).
[Workload](REPRODUCTION_CONFIGURATIONS.md#hardware-and-workloads) and
[erratum](REPRODUCTION_CONFIGURATIONS.md#paper-corrections).

### HNSWLib

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw --profile paper
```

Output: `artifact/results/hnsw-<timestamp>/summary.json`,
`by_dimension["128"].variants.vector_huge.change_percent_vs_baseline` and the
corresponding `"1536"` entry. Expected: about **+9.51% at 128 D** and **+6.56%
at 1536 D** in the evaluator confirmations. Dimensions are reported separately.
[Full configurations and attribution experiments](REPRODUCTION_CONFIGURATIONS.md#hnsw-dimension-and-huge-page-placement).

## 4. Reproduce the main figure observations

These commands generate instrumented diagnostic traces. Their workloads differ
from Table 1 timing runs; use them to inspect layouts. Trace timings are not
throughput evidence. Full-size traces can take minutes or longer to build and
need substantial storage. `--profile smoke` is a smaller functional check and
may not exhibit the same pattern. Addresses, colors and occupancy vary across
runs; compare the stated property rather than individual screenshot pixels.

Figures 1 (components) and 2 (nested allocations) are explanatory illustrations:
there is no measurement command or generated result to compare.

### Figure 3: TPC-C interface screenshot

```bash
bash artifact/run.sh experiment tpcc_bcco --variant baseline --profile paper --out artifact/results/fig3
bash artifact/run.sh gui --database artifact/results/fig3/tpcc_bcco.sqlite --label fig3
```

Output: `artifact/results/fig3/tpcc_bcco.sqlite`. Expected: a populated TPC-C
trace with database allocations and tree nodes. Use 2-MiB page mode and select
a populated time to inspect the interface shown in the paper.

### Figure 4: EFRB prefill allocation pattern

```bash
bash artifact/run.sh experiment ascylib_efrb --variant baseline --profile paper --out artifact/results/fig4
bash artifact/run.sh gui --database artifact/results/fig4/ascylib_efrb.sqlite --label fig4
```

Output: `artifact/results/fig4/ascylib_efrb.sqlite`. Expected: during prefill,
repeated groups of three tree nodes and one operation descriptor. Inspect a
4-KiB page; the paper colors nodes blue and descriptors yellow.

### Figure 5(a–c): EFRB cache occupancy

```bash
bash artifact/run.sh experiment ascylib_efrb --variant baseline --profile paper --out artifact/results/fig5a
bash artifact/run.sh experiment ascylib_efrb --variant prefill-only --profile paper --out artifact/results/fig5b
bash artifact/run.sh experiment ascylib_efrb --variant optimized --profile paper --out artifact/results/fig5c
bash artifact/run.sh gui --database artifact/results/fig5a/ascylib_efrb.sqlite --label fig5a
```

Output: `artifact/results/fig5{a,b,c}/ascylib_efrb.sqlite`. Expected: baseline
node cache-set underuse in (a), parallel prefill alone in (b), and prefill plus
separate node/descriptor arenas in (c), with more even node occupancy. Compare
the cache occupancy view at populated times. Stop the GUI and repeat its command
with `fig5b`, then `fig5c`, to import each database; earlier imports remain listed.
Each result's `trace-configuration.json` records the effective flags. The optional
`segregation-only` variant exposes the fourth factor but is not a Figure 5 panel.

### Figure 6(a–b): BCCO node density

```bash
bash artifact/run.sh experiment tpcc_bcco --variant baseline --profile paper --out artifact/results/fig6a
bash artifact/run.sh experiment tpcc_bcco --variant optimized --profile paper --out artifact/results/fig6b
bash artifact/run.sh gui --database artifact/results/fig6a/tpcc_bcco.sqlite --label fig6a
```

Output: `artifact/results/fig6{a,b}/tpcc_bcco.sqlite`. Expected: BCCO nodes mixed
with database allocations before, and denser node regions after segregation in
the 2-MiB heatmap. Import `fig6b` in the same way. The optimized driver also packs
the lock; this pair is not a segregation-only throughput attribution.

### Figure 7(a–b): mimalloc row layout

```bash
bash artifact/run.sh experiment tpcc_efrb --variant baseline --profile paper --out artifact/results/fig7a
bash artifact/run.sh experiment tpcc_efrb --variant optimized --profile paper --out artifact/results/fig7b
bash artifact/run.sh gui --database artifact/results/fig7a/tpcc_efrb.sqlite --label fig7a
```

Output: `artifact/results/fig7{a,b}/tpcc_efrb.sqlite`. Expected: 48-byte `row_t`
objects with 64-byte alignment before, and padded 64-byte rows after. Import
`fig7b` to compare. Shared reclamation also changes in the optimized variant.

### Figure 8(a–b): HashSkipList bucket fields

```bash
bash artifact/run.sh experiment rocksdb_hsl --variant baseline --profile paper --out artifact/results/fig8a
bash artifact/run.sh experiment rocksdb_hsl --variant optimized --profile paper --out artifact/results/fig8b
bash artifact/run.sh gui --database artifact/results/fig8a/rocksdb_hsl.sqlite --label fig8a
```

Output: `artifact/results/fig8{a,b}/rocksdb_hsl.sqlite`. Expected: expand a bucket
to see padding holes at offsets 36 and 52 before field reordering; the bucket
shrinks from 56 to 48 bytes after. Import `fig8b` to compare. The trace driver
uses the upstream diagnostic snapshot; Table 1 performance uses the historical
snapshot. [Trace scope and all appendix figures](REPRODUCTION_CONFIGURATIONS.md#appendix-figure-and-table-index).

## 5. Check saved results and optional extensions

```bash
bash artifact/run.sh history
python3 artifact/headline-pmu/summarize.py
python3 artifact/headline-pmu/verify_validation.py
```

These are local analyses of saved measurements. `history` prints saved
Valkey/HNSW comparisons; the other commands verify the 400-cell identity matrix
and the separate AIO/HSL validation evidence. See the
[retained logging results and version boundaries](headline-pmu/README.md).
No logging-overhead rerun is required to inspect those results.

Optional procedures are in the supplementary guide:
[HNSW attribution](REPRODUCTION_CONFIGURATIONS.md#attribute-the-hnswlib-improvement),
[C2 logging overhead](REPRODUCTION_CONFIGURATIONS.md#reproduce-logging-overhead-c2),
[other diagnostic traces and LLM export](REPRODUCTION_CONFIGURATIONS.md#generate-traces-and-try-model-assisted-analysis),
and [all performance groups](REPRODUCTION_CONFIGURATIONS.md#run-all-nine-experiments).
The [historical 400-cell rerun](headline-pmu/reproduction/README.md) is a separate,
expensive opt-in (48 hours or more, hundreds of GiB); it is not part of this
guide's smoke check. [Saved-data locations](REPRODUCTION_CONFIGURATIONS.md#saved-experimental-data)
and the [workbook sheet guide](data/README.md) identify the underlying inputs.
