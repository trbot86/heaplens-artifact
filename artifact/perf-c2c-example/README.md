# Inspect measured perf-c2c addresses in HeapLENS

This example supplies a **retained HNSW allocation database and matching
perf-c2c report from the same execution** on Pyke, June 9, 2026. It demonstrates
how measured cache-line addresses select pages and appear in the layout views.
No PMU permission or fresh benchmark is needed. It is a diagnostic example, not
a new performance result or a confirmed source of the paper's original screenshot.

## Prepare the example

From the repository root, with Python 3.10 or newer:

```bash
python3 artifact/perf-c2c-example/example.py verify
python3 artifact/perf-c2c-example/example.py prepare --out artifact/results/perf-c2c-example
```

Output: `artifact/results/perf-c2c-example/hnsw-perf-c2c.sqlite`, the copied
report/provenance logs and `summary.json`. Allow about 400 MB for the unpacked
database. `prepare` requires a new directory and refuses to overwrite earlier
results. It checks file hashes, SQLite integrity and report/database agreement.
`verify` checks the bundled compressed data and report without unpacking them.

Expected: **11 report cache lines, 10 imported cache lines, and three
perf-directed 4-KiB pages**. Address `0x7fec412dc100` is in the report but its page
has no allocation history in this database. It is therefore absent from the
database's `PERF` table. The ten retained lines preserve the report's HITM
percentages and sampled load/store counts; float rounding in SQLite is expected.

## Open it and show the measured addresses

After the Docker build in the [main guide](../README.md):

```bash
bash artifact/run.sh gui --database artifact/results/perf-c2c-example/hnsw-perf-c2c.sqlite --label perf-c2c-example
```

Open <http://localhost:3000>, select `perf-c2c-example.sqlite`, and keep the
default 4-KiB page mode. Move the timeline into a populated interval.

1. Enable **Show HITMs** using the boxing-glove checkbox above the page list.
   Expect ten cache-line markers across these three page addresses:
   `0x55acc2ca9000`, `0x7feac8000000`, and `0x7feb84000000`.
2. Select a marked page to inspect its object layout. Hover a cache-line marker
   to see the report's HITM percentage and sampled loads/stores. For example,
   cache line `0x55acc2ca9500` carries **1.44%, 1,922 loads and 1,206 stores**.
   The first page contains `VisitedList`, `VisitedListPool`, and
   `HierarchicalNSW<float>` allocation histories.
3. Turn HITMs off and enable **Show hot cache lines** using the flame checkbox.
   This selects lines whose sampled loads plus stores meet or exceed the mean
   among the ten imported lines. It is a different predicate from HITM rank.

The perf-directed pages are retained by the page selector. Perf measurements
are aggregated over their recorded interval: moving the allocation timeline
does not turn these totals into time-resolved counters or prove which lifetime
at a reused address caused an access. These markers complement layout evidence.

## What the input represents

[`perf_c2c_report_for_db.txt`](perf_c2c_report_for_db.txt) is the unchanged small
report retained with this execution. Its shared-cache-line table identifies
addresses, total-HITM percentages, and sampled load/store counts. HeapLENS stores
those fields in `PERF(CLADDRESS,HITM,LOADS,STORES)` and associates addresses with
pages. The report's percentage is a share of recorded HITM accesses; it is not
a cache miss rate, a count of all accesses, or proof of false sharing.
See the [Linux perf-c2c manual](https://github.com/torvalds/linux/blob/master/tools/perf/Documentation/perf-c2c.txt)
for the report columns and record/report workflow.

The retained [`perf_c2c_record.log`](perf_c2c_record.log) reports **7.27% lost
samples and 25 lost chunks**. Preserve that limitation when interpreting this
example. [`benchmark.log`](benchmark.log) records a 24-thread instrumented HNSW
diagnostic run with one million 128-D vectors, 100,000 indexed queries, five
query iterations and seed 47. Its timing is not the final uninstrumented
Table 1 comparison. The 11.1-GB raw allocation log, `perf.data` and 1.66-GB full
report are not included in this compact example; this package cannot regenerate
the hardware capture or reprocess the complete original allocation log.

For a new capture, run `perf c2c record` around the **same instrumented process**
that writes the HeapLENS allocation log, then produce the stdio report with
`perf c2c report --stdio`. The native converter accepts that report through
`--perf-file`; its supported input here is the retained Intel total-HITM table
layout. Reports from another execution cannot be paired by virtual address,
and a different perf version/architecture may use different columns. Hardware
support and PMU permissions are prerequisites for recording, not for this
saved-data walkthrough. The artifact does not change host perf policies.

## Validation and provenance

`manifest.json` records exact hashes for the database and retained report/logs.
The prepared database is byte-identical to the retained database. A native
converter test imports the original report using tiny **synthetic allocation
events** at its addresses; that test checks the input format and sampled-page
inclusion, not new hardware measurements. The browser check uses the actual
backend and camera-ready frontend to check the retained pages, HITM/hot toggles
and object tooltips.
