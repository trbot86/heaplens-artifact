# HeapLENS Artifact (ATC '26)

This is the artifact accompanying "HeapLENS: Heap Layout Evaluation & Navigation Suite"
(ATC '26, paper #483). HeapLENS instruments C/C++ applications to log memory
(de)allocations with full type information, samples and clusters the resulting
event log, and visualizes it interactively to help find memory-layout issues
such as cache set underutilization, field scattering, and false sharing.

The system itself (instrumentation, logging, sampling, visualization) lives at
the root of this repository, not under `artifact/`. This directory adds only
what's specific to artifact evaluation: pinned copies of the external
benchmark applications used in the paper's case studies, and scripts that
drive the existing pipeline against them end-to-end.

## Claims and what this artifact reproduces

| Paper claim | Script | Reproduces | Verified |
|---|---|---|---|
| §6.2/Table 1: EFRB tree cache-set underutilization (Fig. 4-5) | `experiments/ascylib_efrb/run.sh` | Diagnostic finding only | Yes (2026-09-20) |
| Appendix B/Table 1: DVY tree | `experiments/ascylib_dvy/run.sh` | Diagnostic finding only | Yes (2026-09-20) |
| Appendix B/Table 1: HJ tree | `experiments/ascylib_hj/run.sh` | Diagnostic finding only | Yes (2026-09-20) |
| §6.3/Table 1: TPC-C with BCCO tree index (Fig. 6-7) | `experiments/tpcc_bcco/run.sh` | Diagnostic finding only | Yes (2026-09-22) |
| §6.3/Table 1: TPC-C with EFRB tree index | `experiments/tpcc_efrb/run.sh` | Diagnostic finding only | Yes (2026-09-22) |
| §6.4: RocksDB HashSkipList memtable | `experiments/rocksdb_hsl/run.sh` | Diagnostic finding only | Not yet run -- see below |
| §6.5, Appendix D: Valkey / HNSWLib LLM-driven case studies | not scripted | Documented only (see below) | n/a |
| §6.2/Fig. 5/Table 1 row 1: EFRB tree fixes (prefill / arenas) | `experiments/ascylib_efrb_bench/run.sh` | **Quantitative ablation** (throughput + hardware-counter deltas) | Mechanically verified (2026-09-21); see caveat below |
| Appendix B.1/Table 3: DVY tree padding (96B/72B/128B/192B) | `experiments/ascylib_dvy_bench/run.sh` | **Quantitative ablation** | Mechanically verified (2026-09-21) |
| Appendix B.2/Table 4: HJ tree allocator (glibc vs jemalloc) | `experiments/ascylib_hj_bench/run.sh` | **Quantitative ablation** | Mechanically verified (2026-09-21) |
| §6.3/Table 1 row 4: TPC-C/BCCO fixes (arenas + row-lock) | `experiments/tpcc_bcco_bench/run.sh` | **Quantitative ablation** | Mechanically verified (2026-09-21) |
| §6.3/Table 1 row 5: TPC-C/EFRB fixes (single-recmgr + row padding) | `experiments/tpcc_efrb_bench/run.sh` | **Quantitative ablation** | Mechanically verified (2026-09-21) |

**TPC-C status:** both experiments build, instrument, and run to full
completion out of the box, producing real, substantial `.sqlite` databases
(at the scripts' own default `THREADS=2`: ~328MB / 4.67M sampled rows for
`tpcc_efrb`, ~255MB / 3.88M rows for `tpcc_bcco`) with exactly the types the
paper describes analyzing -- `node_t<...>` (the actual EFRB/BCCO tree node
type), `row_t`/`Row_lock`/`LockEntry`/`pthread_mutex_t` (the TPC-C row/lock
structures from Fig. 6-7), and `block`/`blockpool`/`blockbag` (SetBench's
EBR reclamation internals, matching the "unexpected buildup of block
objects" anomaly described in paper §6.3). As elsewhere in this artifact,
"diagnostic finding only" applies (see below) -- but for TPC-C specifically,
matching the paper's exact thread/warehouse count or hardware isn't the
point at all: this experiment exists to demonstrate HeapLENS's
instrumentation/sampling/visualization pipeline working end-to-end on the
paper's actual TPC-C case study (the same code, the same data structures,
the same schema), not to reproduce Table 1's throughput numbers, which
would additionally need the paper's follow-up code fix applied. `THREADS=2`
(the scripts' default, not paper-matching) was chosen because it's fast and
because it's what's actually been verified to run to full completion; pass
`THREADS=24` (and optionally `RUN_SECONDS=30`) directly to either `run.sh`
for something closer to the paper's own configuration -- that's been
confirmed to build and run well past schema initialization with no crash,
just not separately timed to full completion. See "Visualizing results"
below for what to look for once you have a database open in the visualizer.

This was previously blocked by a SIGSEGV, whose root cause was
`artifact/vendor/setbench`'s schema data files (`macrobench/benchmarks/
*.txt`) getting CRLF-corrupted by a Windows checkout of this repo's
submodule (`.txt` data files aren't covered by any `.gitattributes` rule,
unlike scripts) -- `getline()`'s failure to strip `\r` caused a parsed
index name to silently mismatch a clean-string-literal lookup elsewhere,
and `std::map::operator[]` resolved that by planting a permanently-null
entry that crashed the first thread to reach it. Getting here also
required: adding a compile-guarded `mem_alloc::alloc` template overload
(now baked into `artifact/patches/setbench-tpcc/macrobench/system/
mem_alloc.h`, delegating to `memhook_interface.h`'s existing
`malloc<T,line,filename>` template rather than duplicating its logic);
fixing wrong runtime CLI flags (`-t`/`-n` need single concatenated tokens
like `-t24`, not separate argv entries -- this was silently zeroing the
thread count); re-pinning `artifact/vendor/setbench` to `5b574d4`, the
commit the paper authors' own reference checkout was actually based on
(previously pinned to an unrelated commit); overlaying ~20 further files
from that same reference checkout with real functional fixes never
committed anywhere fetchable upstream; and uncommenting `bronson_pext_bst_occ`
in the vendored `compile.sh`, which had only `ellen_ext_bst_lf` active. See
the detailed STATUS comment in `tpcc_experiment.sh` for the full writeup,
including why `patches/setbench-tpcc/` is a plain superproject directory
applied at runtime rather than changes committed inside the submodule (the
latter would silently vanish on `git submodule update`, since submodules
are tracked by commit SHA, not working-tree state).

On CPU-constrained machines (e.g. this artifact's own dev/test environment,
a 16-CPU Docker Desktop VM), you may see lines like `ERROR: could not bind
thread N to cpuset ...` during step 6 if `THREADS` exceeds the machine's
actual CPU count -- this is setbench's own thread-pinning code declining to
pin a thread to a nonexistent CPU, harmless and not a sign of failure; lower
`THREADS` to your machine's core count (or fewer) to avoid it.

**RocksDB status:** `experiments/rocksdb_hsl/run.sh` is fully scripted
(pinned to commit `7e272d20`, the parent of `0c7e5bd` / upstream PR
[#13424](https://github.com/facebook/rocksdb/pull/13424) -- i.e. the commit
immediately *before* the paper's fix, so the experiment captures the
pre-fix, 56B HashSkipList bucket layout) but has **not been run
end-to-end** -- it was authored in an environment without a working
clang-14/LLVM/Docker toolchain to iterate against. Unlike the ASCYLIB/TPC-C
scripts, which needed one or two hand-written template-overload patches to
compile, RocksDB's `Allocate`-named methods appear on several unrelated
classes throughout the library (see the detailed comment in
`rocksdb_experiment.sh`), so expect to patch a few more of those than usual
before the instrumented `db_bench` links. Treat this one as a documented
starting point that still needs a debugging pass inside
`docker/ubuntu_22_04`, not a verified reproduction.

**"Diagnostic finding only" means:** each script instruments the *stock,
unmodified* target data structure, runs the workload described in the
paper's methodology (at the paper's own thread/data-size scale for
ASCYLIB; at a smaller, faster scale for TPC-C -- see "TPC-C status" above),
and produces the same kind of sampled SQLite database and cache/page-layout
data behind the paper's figures (e.g. the cache set occupancy pattern in
Figure 5a). It does **not** apply the paper's follow-up code fix (e.g.
separate memory arenas for EFRB tree nodes, `row_t` field reordering) or
reproduce the specific throughput/cache-miss percentages in Table 1 --
those require re-implementing each case study's optimization as a source
patch, which is out of scope for this pass. This was a deliberate scope
decision given the artifact submission timeline; see the "Future work"
note at the end of this file if extending an experiment to full
quantitative reproduction.

## Quantitative ablation experiments (Table 1/3/4 percentages)

The five `*_bench` experiments above are a different, complementary kind of
script from the six diagnostic ones: instead of running HeapLENS's own
instrumentation/sampling pipeline on the *stock* data structure, they build
ASCYLIB's/setbench's own (un-instrumented) benchmark binaries in each of the
paper's described configurations -- stock and with each fix applied -- and
drive them with `perf stat`, exactly as the paper's own
`run_experiment_asplos*.sh` scripts did (see `ASCYLIB_exp/` and
`setbench_exp/` in the paper authors' own development checkouts, not part of
this repo; these were cleaned up and ported into
`artifact/lib/{ascylib,tpcc}_perfbench.sh` and the five `*_bench` experiment
scripts). Each one prints a **human-readable summary table** (mean
throughput and mean hardware-counter rates per variant, averaged over
`REPS` repetitions) at the end, and writes full per-run data to
`artifact/experiments/<name>/results.tsv` plus the same summary to
`artifact/experiments/<name>/summary.txt`. Run all five with:

```sh
artifact/run_perfbench.sh          # paper-scale thread counts, REPS=3
artifact/run_perfbench.sh --quick  # THREADS=4, REPS=1, for a fast pass
```

Each variant's build flags and thread/workload-size parameters are
documented in its own `run.sh` and mapped to the specific paper
figure/table/section they reproduce; `THREADS` and `REPS` (default 3, the
paper itself used 10) are overridable per-experiment env vars, same
convention as the diagnostic experiments.

**Important caveat -- hardware performance counters (cache-miss/LLC-miss/
TLB-miss rates) require the host CPU's performance-monitoring unit (PMU) to
be exposed to the container.** This is a different, stricter requirement
than the `CAP_SYS_ADMIN`/`perf_event_paranoid` permissions most "perf in
Docker" guides describe: it needs the hypervisor underneath Docker to
virtualize or pass through the PMU's MSRs, which most Type-2 hypervisors --
including Docker Desktop's WSL2/Hyper-V backend on Windows, and most cloud
VMs without nested virtualization enabled -- do not do. On such a host,
`perf stat -e cache-misses ...` reports `<not supported>` for *every*
hardware event, even running as root with `perf_event_paranoid` fully
relaxed; this artifact's own dev/test environment is one such host. These
scripts detect this and print `NA (no PMU)` for the affected columns rather
than silently emitting zeroes or fabricated numbers. **Throughput and
page-fault/context-switch numbers are real and unaffected regardless.** To
capture the hardware-counter columns and compare directly against the
paper's Table 1/3/4 percentages, run on bare-metal Linux (or a VM with PMU
passthrough) -- see `artifact/lib/perfstat_common.sh`'s header comment for
the full technical explanation.

"Mechanically verified" above means: each script was run end-to-end inside
`docker/ubuntu_22_04` (this artifact's own dev/test environment, which lacks
PMU access as described above) at reduced thread counts/repetitions and
confirmed to build every variant, run to completion, correctly parse
throughput out of the benchmark's own output, and print a correctly-shaped
summary table -- i.e., the ablations themselves, and this artifact's
plumbing around them, are known-working. The *absolute* throughput deltas
between variants have not been re-validated against the paper's specific
percentages on this host, both because of the PMU limitation above (no
cache/TLB numbers to compare at all) and because a CPU-constrained,
virtualized dev machine with a handful of repetitions is not expected to
closely reproduce numbers measured on a dedicated 24-core Xeon with 10
repetitions -- run at `THREADS`/`REPS` matching your hardware for a
meaningful comparison.

Two adaptations were needed to make setbench's TPC-C ablations (`tpcc_bcco_bench`/`tpcc_efrb_bench`)
portable outside the paper authors' own machine:

- `common/recordmgr/allocator_new.h`'s `-DMEMHOOK_SEG_DS` node-segregation
  fix (used by both TPC-C experiments and `ascylib_efrb_bench`'s conceptual
  equivalent) `dlopen()`s a second, independent copy of an allocator library
  per database table to give tree nodes their own heap arena. The reference
  version hardcoded a developer-machine-specific absolute path
  (`/home/s2ovens/sifter/jemalloc/lib/libjemalloc.so`); this artifact's copy
  (`artifact/patches/setbench-tpcc/common/recordmgr/allocator_new.h`) uses a
  path relative to setbench's own vendored `lib/` directory instead
  (`../lib/libjemalloc.so` / `../lib/libmimalloc.so`, resolved relative to
  the *process's* cwd at dlopen time, which is always `macrobench/`).
- That same `dlopen()` can fail with `cannot allocate memory in static TLS
  block` on modern glibc/jemalloc/mimalloc builds, once the process's small,
  fixed static-TLS surplus is exhausted (glibc reserves this once at
  startup; `dlmopen()` into a fresh namespace does **not** fix this --
  initial-exec TLS is tied to the process's single static region regardless
  of link-map namespace, and namespaces are a small, fixed, easily-exhausted
  resource in their own right when one is created per database table).
  `artifact/lib/tpcc_perfbench.sh` works around it by setting
  `GLIBC_TUNABLES=glibc.rtld.optional_static_tls=4194304` (supported since
  glibc 2.35 / Ubuntu 22.04) for every run.

Valkey and HNSWLib (§6.5, Appendix D) are not scripted: those case studies
used a paid, nondeterministic LLM agent (Codex/GPT-5.5) on specific
cross-NUMA hardware to discover the optimizations, which cannot be captured
by a reproducible script per SysArtifacts' own "Reproduced" badge
definition.

## Hardware / software requirements

The paper's numbers were collected on 2x24-core Intel Xeon Gold 5220R CPUs,
186GiB DRAM, Ubuntu 20.04 (see paper §6.1). The diagnostic experiments here
do not require that exact hardware -- any modern multi-core x86-64 Linux
machine works. The ASCYLIB experiments default to `THREADS=24` (matching
the paper) and can be lowered on smaller machines via the `THREADS`
environment variable; the TPC-C experiments default to a smaller, non-
paper-matching `THREADS=2` regardless of machine size (see "TPC-C status"
above for why). If you raise `THREADS` for TPC-C above your machine's
actual CPU count, expect harmless `could not bind thread N to cpuset`
warnings during step 6 (see "TPC-C status" above).

Expect each ASCYLIB experiment to take a few minutes; each TPC-C
experiment closer to 10-20 minutes at its own `THREADS=2` default (most of
that is a fixed cost -- rebuilding the clang-14/LLVM-based instrumentation
toolchain from scratch and setbench's own C++ build -- not the actual
`THREADS=2` workload run itself, which is fast); and the RocksDB experiment
longer still -- it's the heaviest build of the three (most of the RocksDB
library gets compiled to link `db_bench`). Each TPC-C run at its default
settings produces a `.sqlite` database of roughly 250-350MB (measured:
~328MB for `tpcc_efrb`, ~255MB for `tpcc_bcco`); raising `THREADS` (more
warehouses) or `SAMPLE_PROPORTION` will produce a larger one and take
proportionally longer both to sample and to load in the visualizer.
Budget a few GB of free disk space in the container for build artifacts
plus output databases across all six experiments.

The five quantitative ablation experiments (`artifact/run_perfbench.sh`,
see the dedicated section above) each build several variants sequentially
(3-5 depending on the experiment) and run each `REPS` times (default 3);
budget roughly 5-15 minutes per experiment at default settings on a
multi-core machine, more at paper-scale `THREADS`/`REPS`. They need `perf`,
`numactl`, and `taskset` (all already in `docker/ubuntu_22_04/Dockerfile`)
and, for the hardware-counter columns specifically, a host CPU whose
performance-monitoring unit is exposed to the container -- see the caveat
in "Quantitative ablation experiments" above.

Software dependencies are exactly what's in `docker/ubuntu_22_04/Dockerfile`
at the repository root (clang/LLVM 14, a source build of `perf`, gflags,
tbb, sqlite3, Python 3 + scikit-learn/pandas, etc.). **Use that Docker image**
rather than trying to assemble the toolchain manually.

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

Kick-the-tires (all 6 experiments, shortened workloads, a few minutes total):

```sh
artifact/run_all.sh --quick
```

Full run (longer). Paper-matching thread counts for the ASCYLIB
experiments; **not** paper-matching for TPC-C, which defaults to a smaller,
faster `THREADS=2` regardless -- see "TPC-C status" above for why matching
the paper's thread/warehouse count isn't the point there, and how to
override it if you want to anyway:

```sh
artifact/run_all.sh
```

Or run one experiment directly, e.g.:

```sh
artifact/experiments/ascylib_efrb/run.sh
```

Each script leaves a `<name>.sqlite` database at
`artifact/experiments/<name>/<name>.sqlite`.

The five **quantitative ablation** experiments (see the dedicated section
below) are separate and not included in `run_all.sh` -- they measure
throughput/hardware-counter deltas with `perf stat` rather than producing a
visualizer database, and are run via:

```sh
artifact/run_perfbench.sh          # or: artifact/run_perfbench.sh --quick
```

## Visualizing results

The visualizer itself lives outside `artifact/`, at the repository root;
see the root `README.md`'s "Step 3: Visualization" for full setup
(backend in `sifter_vis_d3/server/`, frontend in `sifter_vis_d3/sifter/`,
each started from within its own subdirectory). A few things that section
doesn't spell out, specific to using it with *this artifact's* output:

1. **Start the backend with a plain `flask --app server run`, no `--port`.**
   The frontend hardcodes `http://localhost:5000` as the backend URL
   (`src/app/page.tsx`, `src/app/vispanels/page.tsx`), which is Flask's own
   default port -- overriding it will silently break the frontend's
   requests.
2. **Copy the database into `sifter_vis_d3/` itself** (the directory
   containing both `sifter_vis_d3/server/` and `sifter_vis_d3/sifter/`) --
   *not* into either of those two subdirectories:
   ```sh
   cp artifact/experiments/tpcc_efrb/tpcc_efrb.sqlite sifter_vis_d3/
   ```
   The backend auto-discovers every `*.sqlite` file directly in that
   directory (`server.py`'s `/get-fnames` route lists it), so any filename
   works -- despite the root README's step 7 saying to copy in
   `allocs.sqlite` specifically (`allocs.sqlite` is just `sifter.sh`'s own
   default output name; a renamed copy works identically), it does not need
   to be renamed.
3. Open `http://localhost:3000` and select the file you copied, by name,
   from the list the frontend shows.
4. To compare against a specific paper figure, filter/search by type name
   in the legend or type list. For the TPC-C experiments: `node_t<...>` is
   the EFRB/BCCO tree's own node type (cf. paper Fig. 6's huge-page density
   heatmap and Fig. 7's row/lock layout); `row_t`, `Row_lock`, and
   `LockEntry` are the TPC-C database's row and lock structures; and
   `block`/`blockpool`/`blockbag` are SetBench's epoch-based-reclamation
   internals (the "unexpected buildup of block objects" anomaly from paper
   §6.3). For ASCYLIB, filter to the tree's own node type (e.g. for the
   EFRB tree) to see the repeating three-nodes-then-an-operation-descriptor
   cache-set pattern from Fig. 4-5.
5. Large databases can take a few minutes to load in the browser (the root
   README notes this too). If a `THREADS=24`-scale TPC-C run (or any other
   experiment run with a larger `SAMPLE_PROPORTION`) feels slow to open,
   re-run the experiment with a lower `SAMPLE_PROPORTION` rather than
   waiting it out -- see "Hardware / software requirements" below for
   default database sizes.

## Vendored dependencies

| Path | Upstream | Pinned commit |
|---|---|---|
| `artifact/vendor/ascylib` | https://github.com/LPD-EPFL/ASCYLIB | `3c2d1a2` |
| `artifact/vendor/setbench` | https://gitlab.com/trbot86/setbench | `5b574d4` (the commit the paper authors' own reference checkout was based on; re-pinned 2026-09-21, was previously and incorrectly `4158107`) |
| `artifact/vendor/rocksdb` | https://github.com/facebook/rocksdb | `7e272d2` (parent of `0c7e5bd`, the paper's HashSkipList fix / [PR #13424](https://github.com/facebook/rocksdb/pull/13424)) |

These are tracked as git submodules despite the repository's top-level
`.gitignore` otherwise ignoring directories with these names (those ignore
rules are for ad-hoc scratch clones used during development); see the
`!/artifact/vendor/` exception near the end of `.gitignore`.

`artifact/vendor/setbench` additionally needs ~24 local patches on top of
its pinned commit to run TPC-C correctly (CRLF-corruption fixes plus real
upstream-of-the-repo functional fixes copied from the paper authors' own,
uncommitted, locally-patched checkout). These live in
`artifact/patches/setbench-tpcc/` as a plain directory tracked directly by
*this* repository, not as changes committed inside the submodule -- a
change only committed in a submodule's own working tree would silently
vanish the moment anyone (including this repo's own `setup.sh`) runs `git
submodule update`, since submodules are tracked by commit SHA, not
working-tree state, and none of these fixes were ever pushed to setbench's
own upstream remote. `tpcc_experiment.sh` copies this directory on top of
each fresh working copy of the vendor source before building; see the
detailed STATUS comment there for exactly what each file fixes and why.

## Status of this artifact (please read before evaluating)

As of 2026-09-20, all three ASCYLIB experiments (`ascylib_efrb`,
`ascylib_dvy`, `ascylib_hj`) were run end-to-end inside
`docker/ubuntu_22_04` and verified to produce real, non-trivial sampled
SQLite databases (hundreds of thousands of sampled events each).

The RocksDB experiment (`rocksdb_hsl`) was added 2026-09-21, after that
verification pass, in an environment without the Docker/clang-14 toolchain
available to exercise it -- see "RocksDB status" above. It has not been run.

On 2026-09-21/22, the TPC-C SIGSEGV that used to block both TPC-C
experiments was root-caused and fixed, by comparing against a reference
copy of the paper authors' own setbench checkout (not part of this repo).
Both experiments were then run end-to-end (at `THREADS=2`) to full
completion, producing real, substantial sampled `.sqlite` databases with
exactly the types the paper describes. See "TPC-C status" above and the
detailed STATUS comment in `artifact/lib/tpcc_experiment.sh` for the full
writeup.

Getting this far required fixing several real bugs, all now fixed in this
branch:

- **`sifter.sh:137`** (`add_includes`, the `--includes-only` step) did
  `cd ./$1`, which silently resolves to a bogus path and fails to `cd`
  (without aborting the script) whenever `$1` is an absolute path -- causing
  the `find . -name '*.c' ...` loop that follows to run from whatever
  directory was left over instead, in practice injecting
  `#include "memhook_interface.h"` into every source file in the whole
  repository, including vendored/unrelated ones. Fixed to `cd -- "$1"`.
- Windows checkouts with `core.autocrlf=true` (e.g. this one) corrupt
  `llvm.sh` and other scripts to CRLF line endings, breaking their shebang
  inside the Linux container. Fixed line endings repo-wide and added
  `.gitattributes` (`*.sh text eol=lf`) so it doesn't recur.
- Ubuntu 22.04's gcc defaults to PIE; ASCYLIB's bundled `ssmem` static lib
  predates that. Needs `-fno-pie`/`-no-pie`.
- Passing `CFLAGS=`/`LDFLAGS=` as `make VAR=...` **command-line** arguments
  freezes those variables in GNU Make -- the target Makefiles' own `+=`
  lines are then silently ignored, stripping out all their real flags. Fixed
  by passing them as environment variables instead (ASCYLIB), or via
  setbench's own purpose-built `xargs` extension variable (setbench, whose
  Makefile does a plain `CFLAGS =`/`LDFLAGS =` reset that would otherwise
  wipe out an environment value too).
- ASCYLIB routes node allocations through its own `ssalloc()`/`ssmem_alloc()`
  functions; `AllocationLoggingCheck` already special-cases these by name and
  rewrites call sites to `ssalloc_s()`/`ssmem_alloc_s()`, and memhook already
  ships real implementations gated behind `-DMEMHOOK_ASCYLIB`, but
  `sifter.sh`'s own memhook build step doesn't know to pass that (it's
  generic across targets). `ascylib_experiment.sh` rebuilds memhook with that
  flag explicitly before the final link.
- Similarly, setbench/DBx1000's `mem_alloc::alloc(size, part_id)` (a plain,
  non-template member function) is targeted by `AllocationLoggingCheck` too
  (`hasName("alloc")`), which rewrites call sites into
  `mem_allocator.alloc<T, line, fileid>(...)` -- but no such template
  *overload* existed. A compile-guarded one is now baked directly into
  `artifact/patches/setbench-tpcc/macrobench/system/mem_alloc.h` (mirroring
  `memhook_interface.h`'s own `malloc<T,line,filename>` free-function
  template, which it delegates to) rather than patched in at runtime; see
  "TPC-C status" above for the full TPC-C writeup.
- Because `sifter.sh`'s internal memhook build (`make -j`, no `clean` first)
  doesn't know when flags need to change between different experiments'
  requirements (e.g. `-DMEMHOOK_ASCYLIB` vs `-DUSE_TEMPLATE`), and GNU Make's
  timestamp-based tracking can't detect a flag-only change, running
  different experiment types back-to-back in the same environment can
  silently link against a stale `libmemhook.so`. Both experiment scripts now
  force a `make clean` in `memhook/` before they need it built their way.
- ASCYLIB's own binaries land in `<ascylib-root>/bin/`, not
  `<tree-dir>/bin/` -- a path bug in this repo's own scripts, now fixed.

On 2026-09-21, the five quantitative ablation experiments (`ascylib_efrb_bench`,
`ascylib_dvy_bench`, `ascylib_hj_bench`, `tpcc_bcco_bench`, `tpcc_efrb_bench`)
were ported from the paper authors' own `run_experiment_asplos*.sh` scripts
and mechanically verified end-to-end inside `docker/ubuntu_22_04` (builds
succeed for every variant, each runs to completion, throughput is parsed
correctly, summary tables print correctly) -- see "Quantitative ablation
experiments" above for the important caveat about this environment lacking
PMU access, so hardware-counter percentages have not themselves been
validated against the paper's Table 1/3/4.

Remaining known gaps: TPC-C is fixed and verified end-to-end at its own
`THREADS=2` default (see "TPC-C status" above); passing `THREADS=24` for
something closer to the paper's own scale is supported and confirmed to
build and run well past schema init with no crash, but hasn't been
separately timed to full completion, so budget generously if you use it.
`SAMPLE_PROPORTION`/`PAGES_PER_TYPE` defaults are reasonable but not
paper-derived, tune per the root README's guidance ("aim for a database
size of around 500MB or less"); RocksDB (`rocksdb_hsl`) hasn't been run
end-to-end at all and will likely need a debugging pass building it inside
`docker/ubuntu_22_04` -- see "RocksDB status" above and the detailed
caveats in `rocksdb_experiment.sh`.

## Future work: full quantitative reproduction

The ASCYLIB (EFRB/DVY/HJ) and TPC-C (BCCO/EFRB) diagnostic experiments now
each have a companion `*_bench` script (see "Quantitative ablation
experiments" above) that applies the paper's described fixes and measures
the resulting throughput/hardware-counter deltas directly, closing most of
what this section used to describe as future work for those five.

What's left:

- **RocksDB HashSkipList (§6.4)** has no ablation script yet, and
  `experiments/rocksdb_hsl/run.sh` itself hasn't been run end-to-end at all
  (see "RocksDB status" above) -- both the diagnostic run and a
  `rocksdb_hsl_bench`-style ablation (swapping `SkipList`'s `prev_`/
  `prev_height_` fields to shrink it from 56B to 48B, per upstream PR
  [#13424](https://github.com/facebook/rocksdb/pull/13424)) are open.
- The ablation scripts' hardware-counter columns (cache-miss/LLC-miss/
  TLB-miss rates) have only been mechanically verified, not compared against
  the paper's actual percentages, since this artifact's own dev/test
  environment lacks PMU access entirely (see the caveat above). Re-running
  `artifact/run_perfbench.sh` at `THREADS`/`REPS` matching a real, non-
  virtualized machine would let someone actually check the reproduced
  percentages against Table 1/3/4.
- Valkey and HNSWLib (§6.5, Appendix D) remain intentionally unscripted --
  see the note above on why (LLM-driven, nondeterministic, specific
  cross-NUMA hardware).
