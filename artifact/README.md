# HeapLENS — ACM ATC 2026 artifact

**Paper:** *HeapLENS: Heap Layout Evaluation & Navigation Suite*, paper 483.

**Latest archived artifact:** [Zenodo release 2026.11.02](https://zenodo.org/records/23905628),
DOI [10.5281/zenodo.23905628](https://doi.org/10.5281/zenodo.23905628).
The [all-versions DOI](https://doi.org/10.5281/zenodo.23206284)
resolves to the latest release. Pinned dependencies are included in the archive.

[Version 2026.10.09](https://zenodo.org/records/23255614) was accepted through
artifact evaluation for the claims in the submitted paper. This update supports
the expanded claims in the accepted paper and includes fixes for missing
allocation records, retirement ordering, complete log writes, and GUI views
that could display stale data.

This checkout targets the final camera-ready paper (October 16 source), including
four-worker EFRB figures, corrected collection, adaptive buffering and final
representative selection. [Integration validation](integration/VALIDATION.md)
distinguishes completed checks from remaining release work.

This guide follows that paper's Table 1 and main figures. Each result
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

References below are the final paper's ten-run means: seven rows use the
retained headline plain-PMU cohort; BCCO and Valkey use the later consistency
cohort, and TPC-C/EFRB uses its factor cohort. The named baseline/combined
workload comparisons are preserved. These cohorts
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
Final paper reference: **+21.1%**, from the retained factor cohort. This frozen
headline driver's saved cohort gives **+20.7%** for the same named comparison;
the two observations are not pooled. Both use 24 warehouses, shared reclamation
plus row padding, with mimalloc and tree segregation fixed. For the complete
command and saved **21.14%** factor calculation, see
[TPC-C factors](camera-ready-reproduction/README.md#tpc-c-factors).

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

These are diagnostic traces, not throughput measurements. Use a fresh output
directory for each command and run traces serially. Fresh allocation addresses
and cluster IDs vary. Compare the stated layout property, not screenshot pixels.
`--profile smoke` is smaller and need not show the paper's pattern. Figures 1–2
are explanatory diagrams and have no experiment command.

The GUI defaults to 128 pages, one million display records and 2,000 buckets.
Unknown trace-clock frequency is shown as ticks. For a trace with a verified
frequency, add `--timestamp-hz HZ` to its `gui --database` command; the value is
saved per database. Do not use the rendering computer's CPU frequency.

### Figures 3–5: TPC-C/HJ interface walkthrough

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh experiment tpcc_hj --variant baseline --profile paper \
  --threads 24 --cpus 0-23 --memory-policy bind --server-node 0 --out artifact/results/fig3-5
bash artifact/run.sh gui --database artifact/results/fig3-5/tpcc_hj.sqlite --label fig3-5
```

Plan: 24 physical cores on node 0, **160 GiB available RAM** for full conversion,
100 GiB local scratch; allow hours (the integrated full capture is not newly
timed); no PMU needed. This uses NO_WAIT, 24 warehouses, 64-byte HJ descriptors
(`LARGE_DES` disabled), retained jemalloc 5.0.1, p=0.01, s=1 and seed 20261009.

Output: `artifact/results/fig3-5/tpcc_hj.sqlite`. Figure 3 is the timeline/legend;
Figure 4 is cache occupancy and cache-line detail; Figure 5 is the page view.
At an early populated time, use 4-KiB pages and show only tree nodes in the
**cache** visibility column while leaving all types visible in pages. Inspect
pages containing the repeating descriptor64 / row48 plus line remainder /
Row_lock64 / node64 sequence. Nodes then appear every fourth cache line.
The final paper's 1.4-s time and page/cluster identifiers describe its saved
capture; they are not universal selections. The final selector can choose
different representative pages from the historical history-only UI capture.

### Figure 6: HNSW measured cache-line markers

```bash
python3 artifact/perf-c2c-example/example.py prepare --out artifact/results/fig6
bash artifact/run.sh gui --database artifact/results/fig6/hnsw-perf-c2c.sqlite --label fig6
```

Plan: saved input; no PMU or native rebuild, 8 GiB RAM and 400 MB disk; minutes.
Output: matching database/report and `summary.json`. Enable **Show HITMs**:
expect ten imported cache lines across three directed pages. The report has
eleven lines; one has no allocation history. This is a retained matching
capture for the same inspection, not a claim of pixel-identical paper artwork.
[Marker meanings, exact addresses and lost-sample limits](perf-c2c-example/README.md).

### Figure 7(a–c): EFRB cache occupancy, early and completed prefill

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh experiment ascylib_efrb --variant baseline --profile paper --threads 4 --cpus 0-3 --memory-policy interleave --out artifact/results/fig7a
HEAPLENS_NUMA=1 bash artifact/run.sh experiment ascylib_efrb --variant prefill-only --profile paper --threads 4 --cpus 0-3 --memory-policy interleave --out artifact/results/fig7b
HEAPLENS_NUMA=1 bash artifact/run.sh experiment ascylib_efrb --variant optimized --profile paper --threads 4 --cpus 0-3 --memory-policy interleave --out artifact/results/fig7c
bash artifact/run.sh gui --database artifact/results/fig7a/ascylib_efrb.sqlite --label fig7a
```

Plan: four physical cores on node 0, 16 GiB available RAM, 10 GiB scratch/trace;
allow 5–30 minutes/trace (estimate); no PMU needed. 262144 initial keys, range
524288, five seconds of read-only work, glibc and dynamic SSMEM; native p=s=1.
Output: `artifact/results/fig7{a,b,c}/ascylib_efrb.sqlite` and configuration receipts.
The three variants are baseline, parallel prefill, and prefill plus separate arenas.

1. Keep modeled L1 at 32 KiB, eight ways and 64-byte lines (64 sets).
2. Zoom into the beginning of the rising node-count curve; choose **early
   prefill**, before the plateau. Keep 2,000 buckets for fine time control.
3. Expand the legend's visibility controls. Right-click `node_t`'s **third
   (cache)** checkbox and choose **Only this type**. Keep the type unexpanded;
   page visibility can still show both nodes and descriptors.
4. Compare early and completed prefill. In the paper's baseline early snapshot,
   15 sets are empty and one has one node. Later allocator chunks fill those
   gaps: completed occupancy is uneven, not partly empty. The changed variants
   make completed occupancy progressively more uniform. Fresh exact counts vary.

Tooltip percentages are each type's share of the set's visible object-line
count, **not cache fullness**. Color is the total visible count normalized
across sets at the selected time: zero gray, maximum red. Including descriptors
can conceal the node imbalance. These are modeled address occupancies, not
hardware-resident lines or measured misses. Import `fig7b` and `fig7c` with the
same GUI command to compare. [Earlier trace corrections](REPRODUCTION_CONFIGURATIONS.md#figure-5-trace-correction)
remain documented under their historical figure number.

### Figure 8: EFRB page during and after prefill

Reuse the `fig7a` database and GUI command above; no additional capture is needed.
Output: the 4-KiB page view. Early prefill shows groups of three 64-byte nodes
and one 64-byte descriptor. Keep that page selected and advance time: dark gray
gaps show retired objects. Paper colors are blue nodes and yellow descriptors;
the type legend identifies colors in a fresh session.

### Figure 9(a–b): BCCO node density

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh experiment tpcc_bcco --variant baseline --bcco-figure --profile paper --threads 24 --cpus 0-23 --memory-policy bind --out artifact/results/fig9a
HEAPLENS_NUMA=1 bash artifact/run.sh experiment tpcc_bcco --variant segregation-only --bcco-figure --profile paper --threads 24 --cpus 0-23 --memory-policy bind --out artifact/results/fig9b
bash artifact/run.sh gui --database artifact/results/fig9a/tpcc_bcco.sqlite --label fig9a
```

Plan: 24 physical cores on node 0, 32 GiB available RAM, 100 GiB local scratch/trace;
allow 30–120 minutes/trace (estimate); no PMU needed. Linux 6.8+ and permitted
`PAGEMAP_SCAN`/`MADV_COLLAPSE` are required by the backing check. A small preflight
fails before the long build if independent jemalloc instances or backing checks
are unavailable. The driver never changes host THP settings.

Output: `artifact/results/fig9{a,b}/tpcc_bcco.sqlite`, typed-node coverage and
allocator/backing receipts. Both arms use jemalloc 5.3.0; the second loads a
distinct instance for nodes. This pair changes segregation only, without packed
locks or shared reclamation. Twenty-four warehouses match twenty-four workers.
Process-local huge-page advice/collapse and mapping snapshots occur outside the
native measured interval. This is diagnostic evidence, not the Table 1 pair.

Select 2-MiB page mode, right-click the **page** visibility checkbox for
`node_t<unsigned long, itemid_t*>`, choose **Only this type**, and **Resample**.
Move to a populated time: expect dispersed low-density node regions before and
fewer denser regions after. Gray means no visible node, not necessarily free
memory. Virtual 2-MiB grouping alone does not prove physical huge-page backing;
use the saved `backing/` receipts for that. The converter uses p=0.02, s=1,
seed 20261010. The paper's saved UI pair had an additional whole-page subsample;
fresh page counts/addresses are therefore not exact screenshot targets.

### Figure 10(a–b): mimalloc row layout

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh experiment tpcc_efrb --variant baseline --profile paper --threads 24 --cpus 0-23 --memory-policy bind --out artifact/results/fig10a
HEAPLENS_NUMA=1 bash artifact/run.sh experiment tpcc_efrb --variant optimized --profile paper --threads 24 --cpus 0-23 --memory-policy bind --out artifact/results/fig10b
bash artifact/run.sh gui --database artifact/results/fig10a/tpcc_efrb.sqlite --label fig10a
```

Plan: 24 physical cores/node 0, 32 GiB free RAM, 100 GiB scratch/trace;
allow 30–120 minutes/trace (estimate); no PMU needed.
Output: `artifact/results/fig10{a,b}/tpcc_efrb.sqlite`. Inspect `row_t`: 48-byte
rows aligned to 64 bytes before, padded 64-byte rows after. The optimized
variant also changes reclamation, so these traces do not isolate its throughput
contribution. Import `fig10b` to compare the row layout.

### Figure 11(a–b): HashSkipList bucket fields

```bash
bash artifact/run.sh experiment rocksdb_hsl --variant baseline --profile paper --out artifact/results/fig11a
bash artifact/run.sh experiment rocksdb_hsl --variant optimized --profile paper --out artifact/results/fig11b
HEAPLENS_CACHE_BUDGET_MB=12000 bash artifact/run.sh gui --database artifact/results/fig11a/rocksdb_hsl.sqlite --label fig11a
```

Plan: the retained diagnostic driver uses 24 workers; 32 GiB free RAM,
100 GiB scratch/trace; allow 1–3 hours/trace (estimate); no PMU needed.
This bounded field-layout diagnostic differs from Table 1's 96-worker mixed
workload. It verifies the same 56-byte versus 48-byte bucket layout.

The GUI command raises the cache-view preflight budget from 4 GiB to about
11.7 GiB (12,000 MiB). One evaluator's trace needed an estimated 5.63 GiB for
cache arrays and response data. This estimate varies with the trace and
Settings, and excludes other server/browser memory; retain the 32-GiB free-RAM
allowance above. With less memory, reduce time buckets as the error suggests.
That changes temporal resolution, not object sizes or field offsets. Raising
this budget does not increase a Docker/WSL memory limit.

Output: `artifact/results/fig11{a,b}/rocksdb_hsl.sqlite`. To inspect the bucket:

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
4. Stop the GUI and repeat the GUI command with `fig11b` in both paths/labels.
   The reordered object is **48 bytes**: `prev_height_` is at offset 36 and
   `prev_` is at offset 40, with neither padding region.

The GUI matches the equivalent `const char*`/`char const*` bucket spellings
used by compiler field metadata and runtime type names. Earlier GUI versions
could show the bucket without attaching its recorded fields. See the
[Historical field and memory notes](REPRODUCTION_CONFIGURATIONS.md#figure-8-field-metadata-and-memory).
The trace driver
uses the upstream diagnostic snapshot; Table 1 performance uses the historical
snapshot. [Trace scope and all appendix figures](REPRODUCTION_CONFIGURATIONS.md#appendix-figure-and-table-index).

## 5. Reproduce logging, selection and engineering results

```bash
python3 artifact/final-paper/summarize.py
```

Output: final Table 3's nine logging rows, the 18.1% adaptive-buffering gain,
and Table 4's four selection rows. This runs in seconds from small saved
evidence with standard Python. [Definitions, cohort boundaries, full JSON
output, selection replay and limits](final-paper/README.md).

The commands below retain the earlier release's observations and validation:

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
