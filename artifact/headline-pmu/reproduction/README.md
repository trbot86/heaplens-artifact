# Rebuild and run the historical headline PMU campaign

This optional Linux host controller rebuilds the recorded workload and logger
versions for ten comparisons, two layout variants, two logging arms and ten
repetitions: **400 cells**. It runs the Python-binding HNSW workload at 128 and
1536 dimensions, not the smaller C++ layout diagnostic. New observations go to
fresh directories; they never replace or join the bundled measurements.

For the fast check of existing results, use the [retained-data guide](../README.md).
The controller below is separate from `artifact/run.sh smoke` and normal artifact
evaluation. Budget **48 hours or more**, at least **400 GiB for archives**,
**100 GiB for live outputs**, and additional space for source/build trees and
images. The observed compressed output was 254.2 GiB. These are provisioning
budgets, not upper bounds. Traces, databases and failed attempts are retained.

## 1. Build the dependency image and inspect the plan

From the repository root in a Linux host shell:

```bash
bash artifact/run.sh build
python3 artifact/headline-pmu/reproduction/launch.py plan
```

Expected: JSON with `cells: 400`, `logging_cells: 200`, and the complete ordered
identity list. `plan` does not contact Docker, create directories or run workloads.

## 2. Select fresh storage and verify the host

Select three separate, non-nested directories outside the artifact. Choose storage
with sufficient space; the paths below are examples. Using local storage instead
of the authors' NFS trace destination can change measured logging overhead.

```bash
RUN_ID="headline-$(date +%Y%m%d-%H%M%S)"
options=(
  --work-root "/var/tmp/$RUN_ID-work"
  --data-root "$HOME/$RUN_ID-data"
  --archive-root "/var/tmp/$RUN_ID-archives"
  --server-node 0 --client-node 1
  --acknowledge-cost
)
python3 artifact/headline-pmu/reproduction/launch.py preflight "${options[@]}"
```

Expected: selected CPU IDs/NUMA nodes and a successful hardware-counter probe.
CPU IDs are discovered from the allowed set. ASCYLIB/TPC-C/ISL/HNSW/Valkey use
distinct physical cores on the selected server node; Valkey needs 24 client cores
on another node. HSL requires 96 logical CPUs, 48 on each selected node. The
controller rejects insufficient resources and does not silently reduce threads.
PMU access requires the same `PERFMON` and NUMA Docker support as the main guide.
It does not change host settings. Builds and runs share an advisory host lock;
ensure other experiments use the same lock or stop them separately.

## 3. Prepare once, then run once

```bash
python3 artifact/headline-pmu/reproduction/launch.py build "${options[@]}"
python3 artifact/headline-pmu/reproduction/launch.py run "${options[@]}"
```

`build` reconstructs the historical source from a SHA-256 manifest plus pinned
small historical source blobs, and builds all selected variants before timing.
The dependency image is pinned by its actual image ID. The source revision is
`7f4f5f20125ad0a2571abc8ddb0e98e13c7ae109`; the archived author overlays and
portable driver changes have separate hashes. Git history and the authors'
machines, paths, SSH keys and existing build trees are not required.

`run` checks that the configuration and driver bytes still match, records the
actual topology and runs serially. Builds, compression and audits do not overlap
measurements. Each stage has an eight-hour limit; each invocation defaults to
a 72-hour total bound (`--timeout-hours` changes it, maximum 168). A failed stage
stops the campaign and preserves its files. There is no automatic retry or resume.
Do not point a new attempt at existing roots or delete failed attempts to retry.

Outputs are host paths:

- Work root: `configuration.json`, `build-state.json`, `run-state.json`, stage
  logs, frozen sources/builds, `topology.json` and final `results.json`.
- Data root: each cell's commands, native logs, PMU CSV, source/binary identities,
  wait reports, completed-cell checks and durable archive receipts.
- Archive root: compressed traces and HSL databases. Each is independently
  decompressed and hash checked before its exact successful raw source is removed.
  Compressed archives are never automatically deleted. Keep independent backups
  according to your storage policy.

Expected final status: `run-state.json` says `completed`, with 400 distinct cells;
`results.json` contains 400 rows and 20 plain/logging comparisons. It reports
`100 * (1 - mean(logging rate) / mean(plain rate))`. Host/storage variation means
the bundled numerical values are reference observations, not pass/fail thresholds.

For an explicitly smaller matrix, add the same selection to **every** command:

```bash
options+=(--apps ascylib_efrb --reps 1)
python3 artifact/headline-pmu/reproduction/launch.py plan --apps ascylib_efrb --reps 1
```

That selects four full-workload cells, not a smoke test or the complete campaign.
Use fresh roots for each selection. It must not be presented as 400-cell evidence.

## Interpretation and validation limits

This recipe reproduces the historical logger versions: HNSW/Valkey have corrected
AIO completion; ASCYLIB/TPC-C/RocksDB use the recorded earlier wait path. It does
not measure every fix in the current release. Instrumentation, wait probing and
storage costs are combined. Negative losses remain observations, not logging
speedup claims. See [semantic scope](../SEMANTIC_REVIEW.md).

Historical HSL uses reader operations divided by the native mixed-workload
completion interval. The additive reader-only/writer timings are documented in
the separate [HSL validation](../hsl-timing/RESULTS.md); the historical recipe does
not silently change that denominator or reconstruct old endpoints.

The portability checks exercise schedules, topology, source identity, failure
handling and archive recovery. Native bounded diagnostics test builds and phase
gates separately. A new complete campaign has not been run to validate this port.
