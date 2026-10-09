# HeapLENS — ACM ATC 2026 artifact

**Paper:** *HeapLENS: Heap Layout Evaluation & Navigation Suite*, paper 483.

**Archived artifact:** [Zenodo release 2026.10.09](https://zenodo.org/records/23255614),
DOI [10.5281/zenodo.23255614](https://doi.org/10.5281/zenodo.23255614).
This version includes the corrected Table 1 command routing, two-worker EFRB
figure defaults, and frozen-source reconstruction repairs, together with the
previous Figure 6/8 fixes. See the [release notes](RELEASE_NOTES_20261009_ROUTING.md)
for validation scope. The [all-versions DOI](https://doi.org/10.5281/zenodo.23206284)
resolves to the latest release. Pinned dependencies are included in the archive.

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

Figure result paths below are **host paths relative to the repository root**.
Table 1 uses explicitly selected absolute host directories.
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

Use the host-side `artifact/table1.py` entry point below after building the Docker
image in section 1. It selects the corrected, frozen drivers under
`artifact/headline-pmu/reproduction`: **dynamic SSMEM in ASCYLIB, RTTI enabled in
RocksDB, and workload-phase hardware counters**. Ten before/after pairs run in
alternating order. No logging measurements run through this entry point.

Preview any selection without building or running workloads:

```bash
python3 artifact/table1.py plan --apps ascylib_efrb
```

Expected: 20 cells, zero logging cells. `reproduce` performs preflight, builds,
then runs serially; it stops on failure and preserves the attempt. Every example
uses fresh absolute host paths outside the checkout. Change both paths to repeat
an experiment. `--data-root` holds live results and RocksDB databases; the
reference RocksDB database storage was NFS. `$HOME` is not necessarily NFS on
another machine: choose and report the actual storage used.

All rows require Linux, Python 3.10+, Docker, kernel >=5.8, permitted PMU access
and NUMA support. The inherited storage checks are conservative: allow **250 GiB
free when work, data and archives share one filesystem**, plus installation;
with separate filesystems the runner checks each reserve. This is a safety
allowance, not expected retained size. The existing build stage still prepares
both plain and logging binaries; only plain binaries are measured here. Build
pruning is not part of this release. Allow hours rather than the earlier short
performance-only estimates; HNSW index construction can dominate. The full
historical 400-cell campaign took 48 hours or more; these subsets have not been
newly timed end to end. [Controller details and limits](headline-pmu/reproduction/README.md).

Output for each command: `<out>/work/results.json`, whose
`performance_comparisons` entry gives `before_mean`, `after_mean` and
`throughput_gain_pct = 100 * (after_mean / before_mean - 1)`. Individual native
logs, actual operation counts and phase-gated `perf.csv` files are under
`--data-root`. CPU selection, source/binary hashes and build configuration are
retained. Counter intervals/denominators are described in
[the semantic review](headline-pmu/SEMANTIC_REVIEW.md).

References below are the current paper's ten-run means: eight rows use the
retained headline plain-PMU cohort; BCCO and Valkey use the later consistency
cohort with the same named baseline/combined workload comparisons. These cohorts
are not pooled. They are observations, not exact-value pass/fail thresholds.
The [older evaluator/factor commands](HISTORICAL_PERFORMANCE_COMMANDS.md) remain
available for their distinct configurations, including four-layout DVY diagnosis;
they are no longer the main Table 1 instructions.

### ASCYLIB/EFRB

```bash
python3 artifact/table1.py reproduce --apps ascylib_efrb \
  --out /var/tmp/heaplens-table1-efrb \
  --data-root "$HOME/heaplens-table1-efrb-data" --acknowledge-cost
```

Plan: 4 physical cores on node 0; 16 GiB RAM; storage/build-time allowances and PMU requirements above.

Output: `/var/tmp/heaplens-table1-efrb/work/results.json`, application `ascylib_efrb`.
Reference gain: **+30.6%**. Four workers, 262144 initial keys, read-only for 5 s; parallel prefill plus segregation versus default.

### ASCYLIB/DVY

```bash
python3 artifact/table1.py reproduce --apps ascylib_dvy \
  --out /var/tmp/heaplens-table1-dvy \
  --data-root "$HOME/heaplens-table1-dvy-data" --acknowledge-cost
```

Plan: 8 physical cores on node 0; 16 GiB RAM; storage/build-time allowances and PMU requirements above.

Output: `/var/tmp/heaplens-table1-dvy/work/results.json`, application `ascylib_dvy`.
Reference gain: **+19.7%**. 192-B versus 96-B nodes, equal huge-page advice, 1048576 initial keys, read-only for 5 s. Huge-page backing and cache topology affect the result.

### ASCYLIB/HJ

```bash
python3 artifact/table1.py reproduce --apps ascylib_hj \
  --out /var/tmp/heaplens-table1-hj \
  --data-root "$HOME/heaplens-table1-hj-data" --acknowledge-cost
```

Plan: 24 physical cores on node 0; 16 GiB RAM; storage/build-time allowances and PMU requirements above.

Output: `/var/tmp/heaplens-table1-hj/work/results.json`, application `ascylib_hj`.
Reference gain: **+6.5%**. glibc after versus jemalloc before, 1048576 initial keys, read-only for 5 s. Expect substantial machine-dependent variation.

### TPC-C/BCCO

```bash
python3 artifact/table1.py reproduce --apps tpcc_bcco \
  --out /var/tmp/heaplens-table1-bcco \
  --data-root "$HOME/heaplens-table1-bcco-data" --acknowledge-cost
```

Plan: 24 physical cores on node 0; 32 GiB RAM; storage/build-time allowances and PMU requirements above.

Output: `/var/tmp/heaplens-table1-bcco/work/results.json`, application `tpcc_bcco`.
Reference gain: **+15.5%**. 24 warehouses; segregation plus packed locks versus default, with jemalloc in both variants. This is not the additional shared-reclaimer variant.

### TPC-C/EFRB

```bash
python3 artifact/table1.py reproduce --apps tpcc_efrb \
  --out /var/tmp/heaplens-table1-tpcc-efrb \
  --data-root "$HOME/heaplens-table1-tpcc-efrb-data" --acknowledge-cost
```

Plan: 24 physical cores on node 0; 32 GiB RAM; storage/build-time allowances and PMU requirements above.

Output: `/var/tmp/heaplens-table1-tpcc-efrb/work/results.json`, application `tpcc_efrb`.
Reference gain: **+20.7%**. 24 warehouses; shared reclamation plus row padding, holding mimalloc and tree segregation fixed.

### RocksDB/HashSkipList

```bash
python3 artifact/table1.py reproduce --apps rocks_hsl \
  --out /var/tmp/heaplens-table1-hsl \
  --data-root "$HOME/heaplens-table1-hsl-data" --acknowledge-cost
```

Plan: 2 NUMA nodes with 48 logical CPUs each; 64 GiB RAM; storage/build-time allowances and PMU requirements above.

Output: `/var/tmp/heaplens-table1-hsl/work/results.json`, application `rocks_hsl`.
Reference gain: **+8.4%**. 95 readers plus one writer; 10M keys, 32-B keys and 128-B values. Uses the native mixed-completion rate, not the separately defined reader-only rate. The application database was on NFS in the reference run; select matching storage with --data-root.

### RocksDB/InlineSkipList

```bash
python3 artifact/table1.py reproduce --apps rocks_isl \
  --out /var/tmp/heaplens-table1-isl \
  --data-root "$HOME/heaplens-table1-isl-data" --acknowledge-cost
```

Plan: 20 physical cores on node 0; 64 GiB available RAM; storage/build-time allowances and PMU requirements above.

Output: `/var/tmp/heaplens-table1-isl/work/results.json`, application `rocks_isl`.
Reference gain: **+8.5%**. 19 readers plus one writer, 10M keys; memory-only configuration. Each trial checks persistence settings.

### Valkey/string cache

```bash
python3 artifact/table1.py reproduce --apps valkey \
  --out /var/tmp/heaplens-table1-valkey \
  --data-root "$HOME/heaplens-table1-valkey-data" --acknowledge-cost
```

Plan: 24 physical cores on each of two NUMA nodes; 32 GiB RAM; storage/build-time allowances and PMU requirements above.

Output: `/var/tmp/heaplens-table1-valkey/work/results.json`, application `valkey`.
Reference gain: **+4.2%**. Combined B1C1_64 versus baseline; 4M keys, 128-B values, SET:GET 1:4, 30 s, 24 client threads, four clients per thread and pipeline 16.

### HNSWLib, 128 dimensions

```bash
python3 artifact/table1.py reproduce --apps hnsw128 \
  --out /var/tmp/heaplens-table1-hnsw128 \
  --data-root "$HOME/heaplens-table1-hnsw128-data" --acknowledge-cost
```

Plan: 24 physical cores on node 0; 32 GiB RAM; storage/build-time allowances and PMU requirements above.

Output: `/var/tmp/heaplens-table1-hnsw128/work/results.json`, application `hnsw128`.
Reference gain: **+9.8%**. Separate vector allocation plus huge-page advice versus baseline; fresh 1M-element index, five measured 100K-query calls after warmup.

### HNSWLib, 1536 dimensions

```bash
python3 artifact/table1.py reproduce --apps hnsw1536 \
  --out /var/tmp/heaplens-table1-hnsw1536 \
  --data-root "$HOME/heaplens-table1-hnsw1536-data" --acknowledge-cost
```

Plan: 24 physical cores on node 0; 32 GiB RAM; storage/build-time allowances and PMU requirements above.

Output: `/var/tmp/heaplens-table1-hnsw1536/work/results.json`, application `hnsw1536`.
Reference gain: **+6.1%**. The same indexed-query protocol at 1536 dimensions; index construction is outside the measured query interval.

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

Plan: 2 worker threads and 2 warehouses by default, without fixed NUMA placement; 32 GiB free RAM; 100 GiB scratch; allow 30–120 min for generation/processing (estimate); no PMU required.

Output: `artifact/results/fig3/tpcc_bcco.sqlite`. Expected: a populated TPC-C
trace with database allocations and tree nodes. Use 2-MiB page mode and select
a populated time to inspect the interface shown in the paper.

### Figure 4: EFRB prefill allocation pattern

```bash
bash artifact/run.sh experiment ascylib_efrb --variant baseline --profile paper --threads 2 --out artifact/results/fig4
bash artifact/run.sh gui --database artifact/results/fig4/ascylib_efrb.sqlite --label fig4
```

Plan: 2 worker threads, without fixed NUMA placement; 16 GiB free RAM; 10 GiB scratch; allow 5–30 min (estimate); no PMU required. The same baseline database can serve Figure 5(a).

Output: `artifact/results/fig4/ascylib_efrb.sqlite`. Expected: during prefill,
repeated groups of three tree nodes and one operation descriptor. Inspect a
4-KiB page; the paper colors nodes blue and descriptors yellow.

### Figure 5(a–c): EFRB cache occupancy

```bash
bash artifact/run.sh experiment ascylib_efrb --variant baseline --profile paper --threads 2 --out artifact/results/fig5a
bash artifact/run.sh experiment ascylib_efrb --variant prefill-only --profile paper --threads 2 --out artifact/results/fig5b
bash artifact/run.sh experiment ascylib_efrb --variant optimized --profile paper --threads 2 --out artifact/results/fig5c
bash artifact/run.sh gui --database artifact/results/fig5a/ascylib_efrb.sqlite --label fig5a
```

Plan: 2 worker threads, without fixed NUMA placement; 16 GiB free RAM; 10 GiB scratch per trace; allow 5–30 min per trace (estimate); no PMU required.

Output: `artifact/results/fig5{a,b,c}/ascylib_efrb.sqlite`. These commands select
baseline in (a), parallel prefill alone in (b), and prefill plus separate
node/descriptor arenas in (c). Expected for (a): **during early prefill**, a
repeating group of one empty (gray), two lower-occupancy (yellow) and one
higher-occupancy (red) node set. A full-profile local trace reproduces this
pattern before the allocator begins its second chunk. Inspect **only nodes**:

1. Keep the modeled L1 geometry at 32 KiB, 8 ways, 64-byte lines (64 sets).
2. Zoom into the beginning of the rising node-count curve. Move the timeline
   handle **within early prefill**, before the curve reaches its plateau.
   Keep the default 2,000 time buckets for fine control. In the local checked
   trace, the pattern appears in buckets 1–30 of 2,000 (the first 1.5% of the
   full timeline); the exact fraction depends on the run.
3. Expand the type legend's visibility controls. Right-click the **third
   checkbox (cache visibility)** on `node_t` and choose **Only this type**.
   Keep `node_t` unexpanded; page visibility can still show both types.
4. Compare node counts across sets. Including `info_t` descriptors can conceal
   the node imbalance and make the entire grid red. Node-only filtering does
   not guarantee empty sets later: the second allocator chunk shifts the
   pattern and can fill the first chunk's gaps. See the
   [trace investigation](REPRODUCTION_CONFIGURATIONS.md#figure-5-trace-correction).

The tooltip percentage is a type's share of that set's visible object-line
count, **not cache fullness**. Color represents the total visible count,
normalized across sets at the selected time: zero is gray and the largest
count is red. Thus 50% of one set and 100% of another can have the same color.
Allocation alignment and chunk boundaries can change the aggregate pattern;
a particular cell's color is not guaranteed. These are modeled address
occupancies, not hardware-resident cache lines or measured misses.

Stop the GUI and repeat its command
with `fig5b`, then `fig5c`, to import each database; earlier imports remain listed.
Inspect their prefill and populated intervals to compare the effects of each change.
Each result's `trace-configuration.json` records the effective flags. The optional
`segregation-only` variant exposes the fourth factor but is not a Figure 5 panel.

For traces generated before the retirement-linkage fix, see the
[Figure 5 trace correction](REPRODUCTION_CONFIGURATIONS.md#figure-5-trace-correction):
filtering isolates node counts, but cannot recover missing retirement events.

### Figure 6(a–b): BCCO node density

```bash
bash artifact/run.sh experiment tpcc_bcco --variant baseline --profile paper --out artifact/results/fig6a
bash artifact/run.sh experiment tpcc_bcco --variant optimized --profile paper --out artifact/results/fig6b
bash artifact/run.sh gui --database artifact/results/fig6a/tpcc_bcco.sqlite --label fig6a
```

Plan: 2 worker threads and 2 warehouses by default, without fixed NUMA placement; 32 GiB free RAM; 100 GiB scratch per trace; allow 30–120 min per trace (estimate); no PMU required.

Output: `artifact/results/fig6{a,b}/tpcc_bcco.sqlite`. Expected: BCCO nodes mixed
with database allocations before, and denser node regions after segregation in
the 2-MiB heatmap. Import `fig6b` in the same way.
Select **Settings → Page settings → 2 MiB**, dismiss Settings and click
**Resample**. Move the time marker well into the trace. Expand the visibility
controls using the arrow in the type-table header, then right-click the middle
(page) checkbox for `node_t<unsigned long, itemid_t*>` and select **Only this
type**. The command now checks for typed 56-byte BCCO nodes and writes
`node-coverage.json`; a database containing only other types fails this check.
Both commands were validated locally in about 5.5 minutes combined; actual
runtime depends on the machine. The baseline GUI and both recorded density
patterns were checked; the optimized GUI was not separately inspected.
See [release validation and remaining limits](RELEASE_NOTES_20261007.md). The optimized driver also packs
the lock; this pair is not a segregation-only throughput attribution.

### Figure 7(a–b): mimalloc row layout

```bash
bash artifact/run.sh experiment tpcc_efrb --variant baseline --profile paper --out artifact/results/fig7a
bash artifact/run.sh experiment tpcc_efrb --variant optimized --profile paper --out artifact/results/fig7b
bash artifact/run.sh gui --database artifact/results/fig7a/tpcc_efrb.sqlite --label fig7a
```

Plan: 2 worker threads and 2 warehouses by default, without fixed NUMA placement; 32 GiB free RAM; 100 GiB scratch per trace; allow 30–120 min per trace (estimate); no PMU required.

Output: `artifact/results/fig7{a,b}/tpcc_efrb.sqlite`. Expected: 48-byte `row_t`
objects with 64-byte alignment before, and padded 64-byte rows after. Import
`fig7b` to compare. Shared reclamation also changes in the optimized variant.

### Figure 8(a–b): HashSkipList bucket fields

```bash
bash artifact/run.sh experiment rocksdb_hsl --variant baseline --profile paper --out artifact/results/fig8a
bash artifact/run.sh experiment rocksdb_hsl --variant optimized --profile paper --out artifact/results/fig8b
HEAPLENS_CACHE_BUDGET_MB=12000 bash artifact/run.sh gui --database artifact/results/fig8a/rocksdb_hsl.sqlite --label fig8a
```

Plan: 24 worker threads, without fixed NUMA placement; 32 GiB free RAM; 100 GiB scratch per trace; allow 1–3 hours per trace (estimate); no PMU required.

The GUI command raises the cache-view preflight budget from 4 GiB to about
11.7 GiB (12,000 MiB). One evaluator's trace needed an estimated 5.63 GiB for
cache arrays and response data. This estimate varies with the trace and
Settings, and excludes other server/browser memory; retain the 32-GiB free-RAM
allowance above. With less memory, reduce time buckets as the error suggests.
That changes temporal resolution, not object sizes or field offsets. Raising
this budget does not increase a Docker/WSL memory limit.

Output: `artifact/results/fig8{a,b}/rocksdb_hsl.sqlite`. To inspect the bucket:

1. Find **`rocksdb::SkipList<char const*, rocksdb::MemTableRep::KeyComparator const&>`**
   in the type table. The shorter `HashSkipListRep` name denotes its owner;
   the type ending in `::Node` denotes an individual list node.
2. Expand the visibility controls, right-click that type's middle (page)
   checkbox, and choose **Only this type**. Click **Resample**, then move the
   time selector into the populated trace.
3. Expand the bucket type's field list and **enable the middle (page) checkbox
   on each indented field row**: the earlier **Only this type** action hid
   those fields as well. Scroll the page list to a page with colored bucket
   allocations and select it for the byte-level detail view. Scroll upward
   over that detail view to magnify the rows. Before reordering, the object is
   56 bytes with four-byte padding regions at **36–39** and **52–55**. Offsets
   are relative to the object's start, which need not be cache-line aligned.
4. Stop the GUI and repeat the GUI command with `fig8b` in both paths/labels.
   The reordered object is **48 bytes**: `prev_height_` is at offset 36 and
   `prev_` is at offset 40, with neither padding region.

The GUI matches the equivalent `const char*`/`char const*` bucket spellings
used by compiler field metadata and runtime type names. Earlier GUI versions
could show the bucket without attaching its recorded fields. See the
[Figure 8 field and memory notes](REPRODUCTION_CONFIGURATIONS.md#figure-8-field-metadata-and-memory).
The trace driver
uses the upstream diagnostic snapshot; Table 1 performance uses the historical
snapshot. [Trace scope and all appendix figures](REPRODUCTION_CONFIGURATIONS.md#appendix-figure-and-table-index).

## 5. Check saved results and additional camera-ready results

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

The [camera-ready reproduction guide](camera-ready-reproduction/README.md) gives
complete commands, output locations and expected values for backend preparation,
UI interaction latency, sampling, TPC-C factors and both HNSW dimensions. Start
with its saved-data verifier; fresh measurements are explicit opt-ins.

A [saved perf-c2c walkthrough](perf-c2c-example/README.md) supplies a matching
HNSW report/database pair, preparation command and expected GUI markers. It
requires no fresh hardware capture.

Other optional procedures are in the supplementary guide:
[HNSW attribution](REPRODUCTION_CONFIGURATIONS.md#attribute-the-hnswlib-improvement),
[C2 logging overhead](REPRODUCTION_CONFIGURATIONS.md#reproduce-logging-overhead-c2),
[other diagnostic traces and LLM export](REPRODUCTION_CONFIGURATIONS.md#generate-traces-and-try-model-assisted-analysis),
and [all performance groups](REPRODUCTION_CONFIGURATIONS.md#run-all-nine-experiments).
The [historical 400-cell rerun](headline-pmu/reproduction/README.md) is a separate,
expensive opt-in (48 hours or more, hundreds of GiB); it is not part of this
guide's smoke check. [Saved-data locations](REPRODUCTION_CONFIGURATIONS.md#saved-experimental-data)
and the [workbook sheet guide](data/README.md) identify the underlying inputs.
