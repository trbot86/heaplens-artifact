# Historical evaluator performance commands

These commands retain the earlier evaluator confirmation configurations and factor
comparisons, including the four-layout DVY check. They are not the current
Table 1 entry point: use [the main guide](README.md#3-reproduce-table-1-performance-comparisons).
ASCYLIB here uses static SSMEM; RocksDB release builds omit RTTI; ASCYLIB/TPC-C
counters cover the whole process. Historical results remain unchanged.

## Earlier comparisons

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

The **Plan** lines give memory/disk planning allowances, not measured minimums;
disk is additional to the shared 20-GB installation. Times exclude the initial
Docker-image build and vary by machine. Core counts describe the default
placement; the [resource table](REPRODUCTION_CONFIGURATIONS.md#per-scenario-resource-planning)
separates observed campaign times from estimates.

### ASCYLIB/EFRB

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_efrb_bench --profile paper
```

Plan: 4 physical cores on node 0; 16 GiB free RAM; 5 GiB scratch; about 5–15 min; counters need kernel ≥5.8 and PMU access.

Output: `artifact/results/ascylib_efrb_bench-<timestamp>/summary.txt`, comparison
`d_both / a_default`. Expected: about **+29.62%**, using four threads and both
parallel prefill and object segregation. [Full configuration](REPRODUCTION_CONFIGURATIONS.md#standalone-efrb-four-threads).

### ASCYLIB/DVY

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_dvy_bench --profile paper
```

Plan: 8 physical cores on node 0; 16 GiB free RAM; 5 GiB scratch; about 5–15 min; counters need kernel ≥5.8 and PMU access; huge-page availability affects the comparison.

Output: `artifact/results/ascylib_dvy_bench-<timestamp>/summary.txt`, compare
`d_192B_pad / a_96B_default`. Expected: about **+18.42%** with equal huge-page
advice and observed backing; check `runs/dvy-page-checks/summary.json`.
[Full configuration and fallback behavior](REPRODUCTION_CONFIGURATIONS.md#dvy-equal-huge-page-advice-for-all-node-layouts).

### ASCYLIB/HJ

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment ascylib_hj_bench --profile paper
```

Plan: 24 physical cores on node 0; 16 GiB free RAM; 5 GiB scratch; about 5–10 min; counters need kernel ≥5.8 and PMU access.

Output: `artifact/results/ascylib_hj_bench-<timestamp>/summary.txt`, compare
`glibc_malloc / jemalloc`. Expected: about **+5.46%**, with substantial variation,
at 24 threads. [Full configuration](REPRODUCTION_CONFIGURATIONS.md#hj-allocator-comparison-at-24-threads).

### TPC-C/BCCO

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment tpcc_bcco_bench --profile paper
```

Plan: 24 physical cores on node 0; 32 GiB free RAM; 10 GiB scratch; about 10–30 min; counters need kernel ≥5.8 and PMU access.

Output: `artifact/results/tpcc_bcco_bench-<timestamp>/summary.txt`, comparison
`c_seg_ds_pack_lock / a_default`. Expected: roughly **+16%**, the submission's
Table 1 target for segregation plus packed locks.
[Workload and allocator details](REPRODUCTION_CONFIGURATIONS.md#hardware-and-workloads).

### TPC-C/EFRB

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment tpcc_efrb_bench --profile paper
```

Plan: 24 physical cores on node 0; 32 GiB free RAM; 10 GiB scratch; about 15–45 min; counters need kernel ≥5.8 and PMU access.

Output: `artifact/results/tpcc_efrb_bench-<timestamp>/summary.txt`, comparison
`e_single_recmgr_mimalloc_fixed / b_mimalloc`. Expected: roughly **+20%**, the
submission's Table 1 target. This combines shared reclamation and padded rows,
holding mimalloc and tree segregation fixed.
[Comparison definitions](REPRODUCTION_CONFIGURATIONS.md#hardware-and-workloads).

### RocksDB/HashSkipList

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh rocksdb --memtable prefix_hash --profile paper
```

Plan: 2 NUMA nodes, 48 logical CPUs each (24 physical cores/node with 2-way SMT); 64 GiB free RAM; 100 GiB scratch; about 30–90 min; no PMU required.

Output: `artifact/results/rocksdb-<timestamp>/summary.json`,
`variants.optimized.change_percent_vs_baseline`. Expected: about **+7.51%** in
the documented five-pair confirmation, using the native rate. New runs also
record reader-only rates and writer completion times; those are distinct metrics.
[Full configuration and timing definitions](REPRODUCTION_CONFIGURATIONS.md#rocksdb-hashskiplist-field-reordering).

### RocksDB/InlineSkipList

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh rocksdb --memtable skip_list --profile paper
```

Plan: 20 physical cores on node 0; **64 GiB available RAM required by the runner**; 10 GiB scratch; about 45–120 min; no PMU required.

Output: `artifact/results/rocksdb-<timestamp>/summary.json`,
`variants.optimized.change_percent_vs_baseline`. Expected: about **+8.61%** for
the memory-only configuration; every trial must pass its persistence check.
[Full configuration](REPRODUCTION_CONFIGURATIONS.md#rocksdb-inline-skiplist-memory-only).

### Valkey/string cache

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh valkey --profile paper
```

Plan: 24 physical cores on each of 2 NUMA nodes; 32 GiB free RAM; 10 GiB scratch; about 15–45 min; no PMU required.

Output: `artifact/results/valkey-<timestamp>/summary.json`,
`variants.B1C1_64.change_percent_vs_baseline`. Expected: about **+4.45%** mean
in the evaluator confirmation (historical mean +4.23%, maximum +5.9%).
[Workload](REPRODUCTION_CONFIGURATIONS.md#hardware-and-workloads) and
[erratum](REPRODUCTION_CONFIGURATIONS.md#paper-corrections).

### HNSWLib

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw --profile paper
```

Plan: 24 physical cores on node 0; 32 GiB free RAM; 10 GiB scratch; about 3–6 hours for both dimensions; no PMU required; huge-page availability affects the comparison.

Output: `artifact/results/hnsw-<timestamp>/summary.json`,
`by_dimension["128"].variants.vector_huge.change_percent_vs_baseline` and the
corresponding `"1536"` entry. Expected: about **+9.51% at 128 D** and **+6.56%
at 1536 D** in the evaluator confirmations. Dimensions are reported separately.
[Full configurations and attribution experiments](REPRODUCTION_CONFIGURATIONS.md#hnsw-dimension-and-huge-page-placement).
