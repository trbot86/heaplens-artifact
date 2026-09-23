# HeapLENS — ACM ATC 2026 artifact

**Paper:** *HeapLENS: Heap Layout Evaluation & Navigation Suite*, ACM ATC 2026,
paper 483. This artifact supplies the C/C++ instrumentation, allocation logger,
trace reconstruction and sampling, interactive GUI, text exporter, retained
application inputs/results, and before/after experiment drivers.

Start with the small verified paths below. See [VALIDATION.md](VALIDATION.md)
for the exact tested scope; packaging a driver does not imply its full paper
experiment has been rerun. [PROVENANCE.md](PROVENANCE.md) distinguishes upstream
source, authors' experimental modifications, retained results, and new runs.

## 1. Requirements and installation

Use x86-64 Linux with Docker Engine, or Docker Desktop with WSL2 for the
functionality checks. Run commands in a Linux/WSL shell from the repository
root. Prefer a native Linux filesystem over `/mnt/c` for compilation speed.
No LaTeX installation is needed. Avoid a native Windows checkout: some upstream filenames/symlinks
are not representable on NTFS.

Allow roughly 20 GB of free disk space for the dependency image and small
builds, and 8–16 GB RAM for basic checks; use at least 32 GB RAM and more
scratch disk for the full application experiments. These are planning
estimates, not measured peak guarantees. Full TPC-C/large trace generation
can require substantially more memory/disk. Build with four jobs by default;
reduce `--jobs` if memory is limited.

The source archive includes vendor content. For a Git checkout, initialize
the pinned submodules **before** building:

```bash
git submodule update --init artifact/vendor/ascylib artifact/vendor/setbench artifact/vendor/rocksdb
git -C artifact/vendor/setbench submodule update --init common/recordmgr tools
bash artifact/run.sh build
```

The container uses Ubuntu 22.04, LLVM/Clang 14.0.6, Python 3.10, Node 18.18.2,
and pinned direct Python/npm dependencies. Its first build needs Internet
access to package registries. Typical first-build time is several minutes,
but depends on download speed. No privileged container or host sysctl change
is required for the quick start. The image is a dependency environment;
the runner mounts this artifact at `/root/sifter`.

## 2. Kick the tires

```bash
bash artifact/run.sh smoke
bash artifact/run.sh gui
```

`smoke` checks dependencies and SQLite integrity, recomputes summaries of
saved results, and regenerates the LLM text export. It does not run large
benchmarks. Expected output includes `Python imports OK`, ten saved runs per
Valkey/HNSW variant, `Export OK`, and a new results directory. With the image
built, this path normally finishes in under a minute on the submission host.

For the GUI, open <http://localhost:3000>, choose `valkey-artifact.sqlite`,
and follow [GUIDED_WALKTHROUGH.md](GUIDED_WALKTHROUGH.md). Move the timeline
away from its initially empty time. The servers bind only to the host's
loopback interface. Ctrl-C stops them. No remote usage telemetry is enabled.

Optional bounded application checks:

```bash
bash artifact/run.sh hnsw --profile smoke
bash artifact/run.sh valkey --profile smoke
bash artifact/run.sh legacy ascylib_efrb_bench --profile smoke
bash artifact/run.sh legacy ascylib_efrb --profile smoke
```

The first two compile separate baseline/candidate copies. Valkey uses 10,000
synthetic keys, two server/client threads, three timed seconds per variant;
HNSW uses 10,000 128-D vectors and 1,000 queries. EFRB uses two threads and
4,096 keys. Builds take minutes. **Smoke speedups are not paper evidence.**

New application output goes to `artifact/results/<command>-<UTC timestamp>/`:
configuration/environment, build logs, per-run data, summary, and pass/fail
status. `--out /root/sifter/artifact/results/NEW_NAME` chooses a new directory;
existing directories are rejected. Legacy paths write under
`artifact/experiments/<name>/`; the entry point refuses to overwrite a prior
working tree/result. Use a fresh checkout for another legacy run.

The GUI also lists `efrb-smoke.sqlite`, a newly generated small teaching trace.
It avoids rebuilding the instrumentation toolchain just to try the interface.

## 3. Experiment-to-paper map

Section/figure references below use the accepted submission, before
camera-ready renumbering. The scripts and configurations are the durable IDs.

| Paper result / capability | Entry point after `bash artifact/run.sh` | Inputs / expected comparison |
|---|---|---|
| Representative-page GUI and text export (§§4–5, §6.5) | `gui`, `export` | Retained Valkey SQLite, compact text, allocation types |
| EFRB (§6.2, Fig. 5, Table 1) | `legacy ascylib_efrb_bench` | Baseline, object segregation, parallel prefill, both |
| DVY (Appendix B, Table 3) | `legacy ascylib_dvy_bench` | 96/72/128/192-byte node-layout variants |
| HJ (Appendix B, Table 4) | `legacy ascylib_hj_bench` | glibc malloc / jemalloc backing the suballocator |
| TPC-C/BCCO (§6.3) | `legacy tpcc_bcco_bench` | Baseline / node segregation / segregation + packed row lock |
| TPC-C/EFRB (§6.3) | `legacy tpcc_efrb_bench` | Allocator, row-padding, and reclamation variants; see caveat below |
| RocksDB HashSkipList (§6.4) | `rocksdb --memtable prefix_hash` | Historical baseline / field reorder + node-alignment reduction |
| RocksDB InlineSkipList (§6.4) | `rocksdb --memtable skip_list` | Historical baseline / align and separate tall nodes |
| Valkey (§6.5 / Appendix D) | `valkey` | Saved baseline / B1C1_64 small-object placement patch |
| HNSWLib (Appendix D) | `hnsw` | Original packed layout / separate aligned vector slab + huge-page advice |
| HNSW rebuttal factorization | `hnsw-factorization --factors hugepage` | Four cells, corrected advice-before-first-touch source; ten blocks in paper mode |
| HNSW separation/alignment follow-up | `hnsw-factorization --factors alignment` | Packed / separate +32-byte offset / separate aligned; six blocks in paper mode |
| Fresh trace generation | `legacy NAME` | NAME = `ascylib_efrb`, `ascylib_dvy`, `ascylib_hj`, `tpcc_bcco`, `tpcc_efrb`, `rocksdb_hsl` |
| Optional model-assisted exploration | See [LLM_EXAMPLE.md](LLM_EXAMPLE.md) | Saved inputs; fresh prompts optional and nondeterministic |

## 4. Paper-size reruns

Explicitly select `--profile paper`; the default is smoke. The application
drivers default to ten repetitions per variant in paper mode; `--reps N`
overrides this and is recorded. This is the **new driver's setting**, not a
claim that every historical auxiliary experiment had ten repetitions.

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh valkey --profile paper
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw --profile paper
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh legacy tpcc_bcco_bench --profile paper
HEAPLENS_NUMA=1 bash artifact/run.sh rocksdb --memtable prefix_hash --profile paper
```

Valkey needs two NUMA nodes with 24 available physical cores each, 4M keys,
128-byte values, 20% SET/80% GET, pipeline 16, four clients/thread, and 30-second
measurements after preload. Server and client nodes default to 0 and 1;
`--server-node` / `--client-node` select them. Persistence is off; networking
is loopback, so a physical NIC is not required for this experiment.

HNSW needs 1M 768-D vectors, 100k indexed queries, 24 build/query threads,
M=16, ef_construction=200, ef=64, k=10, 10k warmup, and five timed iterations.
Allow hours for repeated fresh graph constructions. Report recall alongside
QPS: multithreaded construction is nondeterministic even with a fixed seed.

The two later HNSW analyses have separate commands and source snapshots:

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw-factorization --factors hugepage --profile paper
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw-factorization --factors alignment --profile paper
```

Retained 40-trial and 18-trial data are in `historical/hnsw-factorization/` and
`historical/hnsw-alignment/`. These were collected on Pyke with GCC 13.3 and
Ubuntu 24.04, unlike the artifact container. The new commands preserve the
source/workload/factor structure, not an identical historical software stack.
For huge-page mechanism claims inspect live mappings/THP backing on the target
host; neither a successful `madvise` nor a tiny smoke run establishes backing.

RocksDB's paper profile follows the retained 18-thread protocol (17 reader
threads plus background writer), 10M keys, 64-byte keys, 256-byte values,
128 MiB write buffers, disabled WAL, and 10-second measured phase. Disk and
allocator effects matter; exact performance is not guaranteed on a different
machine. Fresh databases live only inside the new results directory.

**Protocol discrepancy to resolve:** the retained RocksDB script specifies
64/256-byte keys/values, but Section 6.4's prose says 32/128. The default
replays the script; `--rocks-key-size 32 --rocks-value-size 128` selects the
prose sizes. Do not describe either as reconciled historical ground truth.

One umbrella command runs all nine available before/after experiment groups:

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh all-performance --profile paper
```

Run individual groups first. The umbrella stops on failure, and is not a
claim to cover every figure, sampling study, overhead measurement, or LLM
control in the paper. It can take many hours and substantial disk space.

`HEAPLENS_NUMA=1` relaxes the container's seccomp filter for NUMA placement;
`HEAPLENS_PERF=1` grants PERFMON, not blanket privileged mode. Use these only
on an appropriate dedicated evaluation host. Host PMU policy may still deny
access. Scripts do not change it; request administrator help if needed.
VM/WSL results are functionality checks, not substitutes for bare-metal PMU
measurements. For throughput-only legacy paper runs, prefix the wrapper with
`PERFBENCH_PERF=off`. Missing counters must remain `NA`, never zero.

## 5. Scope, interpretation, and extension

- `history` summarizes retained original data; it does not rerun experiments.
  Raw configurations and records are distributed for independent analysis.
- The legacy performance helper reports whole-process counter **totals**,
  including prefill. It does not reproduce measurement-window per-operation
  counters. Full counter fidelity remains a validation task.
- The historical TPC-C/EFRB mimalloc comparison also changes the segregation
  flag in one variant; do not present it as a pure one-factor padding study.
- Original HNSW huge-page advice is not proof of huge-page backing. The later
  rebuttal factorization used corrected first-touch placement and a different
  environment; do not reinterpret the original replay as that factorization.
- Fresh trace generation is separate from timing uninstrumented optimized
  applications. An instrumented run's throughput is not an optimization result.
- For another C/C++ application, follow the root README's instrumentation
  procedure, add custom allocation APIs where needed, and preserve lifetimes
  of nested regions. Use new output folders and inspect nonempty type/allocation
  records before opening the GUI. Source instrumentation is not a one-command
  guarantee for arbitrary custom allocators.

See [VALIDATION.md](VALIDATION.md) for verified paths and remaining gaps.

Sean's latest additions are retained: `data/paper_data.xlsx` with its own
[sheet guide](data/README.md), the RocksDB instrumentation-repair helpers,
`export_llm_data.sh`, and the optional native GUI launcher
`sifter_vis_d3/setup_and_launch.sh`. The documented primary entry point is
`artifact/run.sh`; the two older `rocksdb_*_bench/run.sh` names now delegate
to the restored historical-source driver (default smoke, explicit paper
profile). The new source snapshot and patch are essential: the upstream
diagnostic tree alone does not implement these experimental flags.

Questions during evaluation should use the conference's anonymous discussion
channel. No reviewer accounts, identities, or activity need be reported to us.
