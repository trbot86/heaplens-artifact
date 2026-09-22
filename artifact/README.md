# HeapLENS Artifact (ATC '26)

This is the artifact accompanying "HeapLENS: Heap Layout Evaluation &
Navigation Suite" (ATC '26, paper #483). HeapLENS instruments C/C++
applications to log memory (de)allocations with full type information,
samples and clusters the resulting event log, and visualizes it
interactively to help find memory-layout issues such as cache set
underutilization, field scattering, and false sharing.

The system itself (instrumentation, logging, sampling, visualization) lives
at the root of this repository, not under `artifact/`. This directory adds
only what's specific to artifact evaluation: pinned copies of the external
benchmark applications used in the paper's case studies, and scripts that
drive the existing pipeline against them end-to-end.

There are two kinds of experiments here:

- **Visualization experiments** (`experiments/<name>/run.sh`): instrument a
  stock, unmodified target data structure with HeapLENS and produce a
  sampled `.sqlite` database to open in the visualizer, reproducing the data
  behind the paper's figures.
- **Performance experiments** (`experiments/<name>_bench/run.sh`): build the
  target's own (un-instrumented) benchmark binaries in each of the paper's
  described configurations -- stock and with each fix applied -- and measure
  throughput/hardware-counter deltas with `perf stat`, reproducing the
  percentages in Table 1/3/4.

## What's reproduced

| Paper claim | Script | Reproduces |
|---|---|---|
| §6.2/Fig. 4-5: EFRB tree cache-set underutilization | `experiments/ascylib_efrb/run.sh` | Visualization data |
| Appendix B: DVY tree | `experiments/ascylib_dvy/run.sh` | Visualization data |
| Appendix B: HJ tree | `experiments/ascylib_hj/run.sh` | Visualization data |
| §6.3/Fig. 6-7: TPC-C with BCCO tree index | `experiments/tpcc_bcco/run.sh` | Visualization data |
| §6.3: TPC-C with EFRB tree index | `experiments/tpcc_efrb/run.sh` | Visualization data |
| §6.4: RocksDB HashSkipList memtable | `experiments/rocksdb_hsl/run.sh` | Visualization data |
| §6.2/Fig. 5/Table 1 row 1: EFRB tree fixes (prefill / arenas) | `experiments/ascylib_efrb_bench/run.sh` | Performance experiment |
| Appendix B.1/Table 3: DVY tree padding (96B/72B/128B/192B) | `experiments/ascylib_dvy_bench/run.sh` | Performance experiment |
| Appendix B.2/Table 4: HJ tree allocator (glibc vs jemalloc) | `experiments/ascylib_hj_bench/run.sh` | Performance experiment |
| §6.3/Table 1 row 4: TPC-C/BCCO fixes (arenas + row-lock) | `experiments/tpcc_bcco_bench/run.sh` | Performance experiment |
| §6.3/Table 1 row 5: TPC-C/EFRB fixes (single-recmgr + row padding) | `experiments/tpcc_efrb_bench/run.sh` | Performance experiment |
| §6.5, Appendix D: Valkey / HNSWLib | not scripted | LLM-driven case study; not reproducible as a script (see below) |

None of the visualization experiments apply the paper's follow-up code
fixes -- for the quantitative Table 1/3/4 percentages, see each experiment's
`_bench` counterpart instead.

Valkey and HNSWLib (§6.5, Appendix D) aren't scripted: those case studies
used a nondeterministic LLM agent on specific hardware to discover the
optimizations, which isn't reproducible as a script.

## TPC-C notes

Both TPC-C experiments (visualization and performance) default to
`THREADS=2` rather than the paper's own thread/warehouse count, since the
point of the TPC-C experiments here is to demonstrate the pipeline working
on the paper's actual case study, not to reproduce Table 1's exact numbers
at scale. Pass `THREADS=24` (and, for the visualization experiments,
`RUN_SECONDS=30`) for something closer to the paper's configuration. If
`THREADS` exceeds your machine's core count you'll see harmless
`could not bind thread N to cpuset` warnings.

## Performance experiments

**Cache/TLB/LLC-miss columns need hardware performance-counter (PMU) access,**
which most Type-2 hypervisors don't expose to containers (including Docker
Desktop's WSL2/Hyper-V backend on Windows). On such hosts `perf stat` prints
`<not supported>` for every hardware event; these scripts detect that and
print `NA (no PMU)` instead of fabricating a number. Throughput and
page-fault/context-switch numbers are unaffected. Run on bare-metal Linux
(or a VM with PMU passthrough) to get the hardware-counter columns.

## Hardware / software requirements

Any modern multi-core x86-64 Linux machine works; the paper's own numbers
were collected on 2x24-core Intel Xeon Gold 5220R CPUs (§6.1). ASCYLIB
experiments default to `THREADS=24`; TPC-C defaults to `THREADS=2` (see
above). Each visualization experiment takes a few minutes to run except
TPC-C (10-20 min, mostly toolchain/build time) and RocksDB (heaviest build).
Each performance experiment takes roughly 5-15 minutes at default settings.
Budget a few GB of free disk space for build artifacts and output databases.

Software dependencies are exactly what's in
`docker/ubuntu_22_04/Dockerfile` at the repository root (clang/LLVM 14, a
source build of `perf`, gflags, tbb, sqlite3, Python 3 +
scikit-learn/pandas, `numactl`, etc.). **Use that Docker image** rather than
assembling the toolchain manually.

## Setup

```sh
cd docker/ubuntu_22_04
sudo ./build_image_and_launch.sh --name sifter-artifact
# inside the container:
cd /root/sifter
artifact/setup.sh
```

`artifact/setup.sh` initializes the three pinned vendor submodules
(`artifact/vendor/ascylib`, `artifact/vendor/setbench` plus its own nested
submodules, `artifact/vendor/rocksdb`) and sanity-checks the toolchain is on
`PATH`.

## Running experiments

Kick-the-tires (all 6 visualization experiments, shortened workloads):

```sh
artifact/run_all.sh --quick
```

Full run (paper-scale thread counts for ASCYLIB; TPC-C stays at `THREADS=2`
by default -- see "TPC-C notes" above):

```sh
artifact/run_all.sh
```

Or run one experiment directly, e.g. `artifact/experiments/ascylib_efrb/run.sh`.
Each leaves a `<name>.sqlite` database at
`artifact/experiments/<name>/<name>.sqlite`.

Performance experiments are separate (see above) and not included in
`run_all.sh`:

```sh
artifact/run_perfbench.sh
```

## Visualizing results

The visualizer lives outside `artifact/`, at the repository root; see the
root `README.md`'s "Step 3: Visualization" for full setup (backend in
`sifter_vis_d3/server/`, frontend in `sifter_vis_d3/sifter/`). Specifics for
this artifact's output:

1. Start the backend with a plain `flask --app server run` (no `--port` --
   the frontend hardcodes `http://localhost:5000`).
2. Copy the database into `sifter_vis_d3/` itself (not either subdirectory):
   ```sh
   cp artifact/experiments/tpcc_efrb/tpcc_efrb.sqlite sifter_vis_d3/
   ```
   Any filename works -- the backend lists every `*.sqlite` file it finds
   there.
3. Open `http://localhost:3000` and select the file by name.
4. Filter by type name to match a paper figure. TPC-C: `node_t<...>` is the
   tree's node type, `row_t`/`Row_lock`/`LockEntry` are the row/lock
   structures, `block`/`blockpool`/`blockbag` are SetBench's
   epoch-based-reclamation internals. ASCYLIB: filter to the tree's own node
   type to see the cache-set pattern from Fig. 4-5.
5. Large databases can take a few minutes to load; lower `SAMPLE_PROPORTION`
   and re-run if that's a problem.

## Vendored dependencies

| Path | Upstream | Pinned commit |
|---|---|---|
| `artifact/vendor/ascylib` | https://github.com/LPD-EPFL/ASCYLIB | `3c2d1a2` |
| `artifact/vendor/setbench` | https://gitlab.com/trbot86/setbench | `5b574d4` |
| `artifact/vendor/rocksdb` | https://github.com/facebook/rocksdb | `7e272d2` (parent of `0c7e5bd`, the paper's HashSkipList fix / [PR #13424](https://github.com/facebook/rocksdb/pull/13424)) |

These are tracked as git submodules; see the `!/artifact/vendor/` exception
in `.gitignore`.

`artifact/vendor/setbench` additionally needs the local patches in
`artifact/patches/setbench-tpcc/` (fixes to schema data files and
macrobench source, plus a `common/recordmgr/allocator_new.h` node-arena
fix) to run TPC-C correctly. These are a plain directory tracked by this
repository rather than changes committed inside the submodule, since a
submodule only tracks a commit SHA, not working-tree state.
`tpcc_experiment.sh`/`tpcc_perfbench.sh` copy this directory onto each fresh
working copy of the vendor source before building.

## Known gaps

- Valkey and HNSWLib (§6.5, Appendix D) are intentionally unscripted (see
  above).
