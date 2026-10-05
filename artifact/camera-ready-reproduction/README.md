# Camera-ready result reproduction

Run commands from the repository root. This guide adds the backend preparation,
browser latency, sampling and controlled-factor results to the
[Table 1 and figure guide](../README.md). Every study has a command, an output
and a reference observation below. The references come from separate, identified
campaigns; they are never pooled. Timing varies with the machine and browser.

## Check retained evidence first

Python 3.10 or newer is sufficient; these commands need neither Docker nor a
browser and launch no measurements:

```bash
python3 artifact/camera-ready-reproduction/reproduce.py plan
python3 artifact/camera-ready-reproduction/reproduce.py verify
```

Output: JSON on standard output. `verify` checks the compressed assets and saved
evidence against `manifest.json`, recomputes the backend/UI medians and sampling
counts from individual rows, and recomputes application/factor/overhead ratios
from the retained independent-audit means. That last calculation is an
arithmetic check, not a new audit of the raw application trials.

The package contains the retained inputs and frozen study sources, so none of
the commands depend on the authors' `/tmp` directories, SSH hosts or checkouts.
The approximately 35-MB compressed package expands to about 520 MB. The saved
measurements and both archives remain untouched. Every command below requires a
**new output directory**; choose another name to repeat it. Failed attempts and
their logs remain available; there are no automatic retries.

Build the dependency image as in the main guide, then run the bounded component
checks (several minutes, at least 4 GiB free disk):

```bash
bash artifact/run.sh build
python3 artifact/camera-ready-reproduction/reproduce.py check --out artifact/results/cr-check
```

Output: `artifact/results/cr-check/summary.json` with `status: passed`, plus
`cleanup.json` and `evidence/`. This compiles the frozen native converter, runs
backend synthetic equality tests, checks browser-harness syntax and generates a
synthetic fixture. It does not execute a latency or retained-input campaign.
Linux with local Docker is the supported command environment. The controller
records the dependency image ID, source/input hashes and executed commands.

## Backend preparation: spatial updates and temporal prefix sums

```bash
python3 artifact/camera-ready-reproduction/reproduce.py backend --out artifact/results/cr-backend --acknowledge-cost
```

Output: `artifact/results/cr-backend/summary.json` and individual rows under
`evidence/`; `evidence/results.json` contains all 32 cells. Expect eight warmups
and 24 measured runs: two retained inputs, four implementations, three measured
repetitions. Complete prepared payload hashes must match within each input.

| Spatial updates / temporal accumulation | Valkey cache / complete preparation (s) | BCCO cache / complete preparation (s) |
| --- | ---: | ---: |
| Enumerated / direct | 100.77 / 105.99 | 6.51 / 10.25 |
| Range / direct | 13.35 / 18.63 | 5.58 / 9.37 |
| Enumerated / prefix | 5.85 / 11.06 | 19.97 / 23.72 |
| Range / prefix | 3.61 / 8.90 | 7.01 / 10.81 |

These are medians of three trials from September 29. Complete preparation
includes database reading, statistics, page/cache preparation and JSON
serialization, excluding HTTP and browser work. BCCO's combined implementation
is slightly slower than its baseline: retain that result. The 2,000 time buckets,
128-page/100,000-record budgets and seed 20260929 are fixed. Workers have two CPU
equivalents, 12 GiB RAM and one BLAS/OpenMP thread; each is limited to 180 seconds
and the controller stops launching cells after 30 minutes. Have at least 4 GiB
free disk and sufficient host RAM. Reference host: i7-14700KF, Linux under WSL2.

## Browser latency

These studies replay fixed payloads over HTTP against the frozen before/after
frontends. They isolate browser work; they do not include database conversion
or backend preparation. Browser version, CPU, GPU acceleration and compositor
conditions affect timings. The reference used Windows Edge 154.0.4258.37 on an
i7-14700KF with an RTX 3080. A different environment is a portability measurement,
not a confirmation under identical conditions.

Install the host-side browser harness with Node.js 20 or newer. This optional
setup downloads Chromium; browser OS dependencies must already be installed.
It does not change host packages or policies. This package uses Playwright Core
1.62.1. To use an existing Edge/Chromium instead, pass its
absolute executable path to `--browser` in the study command.

```bash
npm install --prefix artifact/results/browser-tools --save-exact playwright-core@1.62.1
node artifact/results/browser-tools/node_modules/playwright-core/cli.js install chromium
```

Run sequentially with localhost ports 5000 and 3000–3003 free. Each command
starts private Docker services, uses the explicitly selected host browser and
stops its own services at completion or failure. Allow 24 GiB host RAM and at
least 4 GiB disk; startup/compilation is outside the reported interaction times.

### Selected-time-bucket cache visibility

```bash
python3 artifact/camera-ready-reproduction/reproduce.py ui-toggle --out artifact/results/cr-ui-toggle --browser "$(node -e 'console.log(require(process.cwd()+"/artifact/results/browser-tools/node_modules/playwright-core").chromium.executablePath())')" --playwright "$PWD/artifact/results/browser-tools/node_modules/playwright-core" --environment-note "Local Chromium; record GPU/display conditions with this run" --acknowledge-cost
```

Output: `artifact/results/cr-ui-toggle/summary.json`, `browser.json` and
`evidence/browser.jsonl`, with screenshots. Expected median cache-visibility
click response: Valkey/52 pages **568.45 → 78.45 ms**, BCCO/17 pages
**488.00 → 52.10 ms**, and BCCO/128 pages **570.60 → 136.55 ms**. Each value is
the median of three trial medians. All 18 browser contexts must complete, and
the corresponding rendered states and text exports must match. The viewport
is 1280 × 720. The browser controller is limited to 30 minutes.

### Detail view: coalesce contiguous bytes within cache lines

```bash
python3 artifact/camera-ready-reproduction/reproduce.py ui-detail --out artifact/results/cr-ui-detail --browser "$(node -e 'console.log(require(process.cwd()+"/artifact/results/browser-tools/node_modules/playwright-core").chromium.executablePath())')" --playwright "$PWD/artifact/results/browser-tools/node_modules/playwright-core" --environment-note "Local Chromium; record GPU/display conditions with this run" --acknowledge-cost
```

Output: `artifact/results/cr-ui-detail/summary.json`, `browser.json` and
`evidence/{baseline,optimized}/browser.jsonl`, with screenshots. Expected on
the dense-64K fixture: **18,751.2 → 381.0 ms** for a 65,536-byte selection;
object rectangles fall from 65,536 to 2,048. DOM checks include two clip-path
rectangles, hence 65,538 and 2,050. Dense-1M is **21,394.9 → 412.3 ms** and
live-1M is **3,077.2 → 1,161.7 ms** for the same selected byte extent.

Each arm has three fresh-browser trials per fixture plus a discarded warmup.
The viewport is 1440 × 1000; the browser uses its default JavaScript heap limit.
Each trial is bounded to 180 seconds and no further trials launch after 30
minutes. The fixtures contain synthetic 32-byte objects, with retained
cache/statistics panels as fixed controls. They deliberately bypass normal
selection budgets to test rendering scale. They are not new application traces.
Both UI studies measure response to the second animation frame, a rendering
proxy rather than compositor presentation latency.

## Sampling: rare and common allocation patterns

```bash
python3 artifact/camera-ready-reproduction/reproduce.py sampling --out artifact/results/cr-sampling --acknowledge-cost
```

Output: `artifact/results/cr-sampling/summary.json`,
`evidence/all-results.json` (100 Valkey rows), per-trial payloads/oracle scores,
and `evidence/efrb-r00/` through `efrb-r19/`. Expect **20/20 rare `raxNode`
and 20/20 common `robj` successes at each setting** `(p,s) = (0.001,1),
(0.01,1), (0.1,1), (0.1,2), (1,1)`, and **20/20 EFRB layout successes**.
Every Valkey trial must satisfy the native per-type page floor and the GUI's
128-page/100,000-record limits. Seeds are 20260928–20260947.

This reprocesses one retained Valkey binary log (1,016,169 events) and one
retained EFRB database using the frozen converter, sampler and scoring oracles.
It does not generate 120 new application traces, test arbitrary workloads or
establish guaranteed retention. `p` is native random retention before floors;
`s` sets the native per-type page floor, not the GUI budget. Allow at least
16 GiB free disk; the container has four CPU equivalents, 12 GiB RAM and a
three-hour limit. See `saved/sampling-protocol.json` for the recorded protocol.

## Controlled factors and final application references

The final September 30–October 1 application campaign has 320 trials, including
the TPC-C factors; a separate HNSW factor campaign has 116 trials. Ratios below
use arithmetic mean throughput. These are descriptive results, not confidence
intervals or guaranteed reproduction tolerances. The main camera-ready README
uses these references; older evaluator confirmations remain in the
[full reference guide](../REPRODUCTION_CONFIGURATIONS.md).

### TPC-C factors

```bash
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment tpcc_bcco_bench --profile paper --tpcc-factors full --out artifact/results/cr-bcco-factors
HEAPLENS_NUMA=1 HEAPLENS_PERF=1 bash artifact/run.sh experiment tpcc_efrb_bench --profile paper --tpcc-factors full --out artifact/results/cr-efrb-factors
```

Output: each directory's `summary.txt`, `results.tsv`, `protocol.json` and
per-trial logs. Ten repetitions per variant, 24 physical node-0 cores with
local memory. BCCO's five variants separate segregation, packing the row lock,
their combination and adding shared reclamation. EFRB's seven variants include
the two extra cells required to hold mimalloc and segregation fixed.

| Ratio (after / before) | Expected gain |
| --- | ---: |
| BCCO `b_seg_ds / a_default` | +2.81% |
| BCCO `d_lock_only / a_default` | +11.12% |
| BCCO `c_seg_ds_pack_lock / a_default` | +15.93% |
| BCCO `e_combined_single_recmgr / c_seg_ds_pack_lock` | +0.0062% |
| EFRB `f_padding_only_segregated / b_mimalloc` | +0.52% |
| EFRB `g_single_recmgr_mimalloc / b_mimalloc` | +19.51% |
| EFRB `e_single_recmgr_mimalloc_fixed / b_mimalloc` | +21.14% |

The tiny BCCO shared-reclaimer difference does not establish a meaningful
effect. EFRB's historical `c_mimalloc_fixed` also changes segregation and must
not be used as the controlled padding-only cell. ASCYLIB/EFRB's four factors
already run in its main README command (`a_default`, `b_obj_seg`,
`c_mt_prefill`, `d_both`). Figure 5(b) uses the separate **trace** command
`--variant prefill-only` given in the main guide.

### HNSW layout, huge-page advice and alignment controls

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw-factorization --factors hugepage --dim 128 --profile paper --out artifact/results/cr-hnsw-huge-128
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw-factorization --factors hugepage --dim 1536 --profile paper --out artifact/results/cr-hnsw-huge-1536
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw-factorization --factors alignment --dim 128 --profile paper --out artifact/results/cr-hnsw-align-128
HEAPLENS_NUMA=1 bash artifact/run.sh hnsw-factorization --factors alignment --dim 1536 --profile paper --out artifact/results/cr-hnsw-align-1536
```

Output: each directory's `summary.json`, CSV trial rows, `protocol.json`, and
the factor summarizer's report. Huge-page studies have ten four-cell blocks;
alignment studies have six three-cell blocks. They use one million vectors,
100,000 indexed queries, 10,000 warmups, five query iterations and 24 physical
cores. These are expensive, multi-hour runs; execute them sequentially.

| Comparison | 128 D gain | 1536 D gain |
| --- | ---: | ---: |
| `hugepage / baseline` | +2.59% | +1.82% |
| `vector_soa64 / baseline` | +3.21% | +2.32% |
| `both / baseline` | +9.75% | +6.62% |
| `separated_unaligned32 / packed` | −5.28% | +0.77% |
| `separated_aligned64 / packed` | +3.32% | +2.29% |
| `separated_aligned64 / separated_unaligned32` | +9.07% | +1.51% |

The saved summarizer also reports paired geometric ratios and interactions;
keep that statistic separate from ratios of arithmetic means above. The chosen
32-byte offset is one alignment control, not arbitrary unaligned allocation.
Historical per-trial huge-page backing was not recorded. New runs' advice or
mapping diagnostics cannot retroactively establish it. Indexed self-label hits
are not ground-truth top-k ANN recall.

### Stock logger overhead and the separate headline campaign

```bash
HEAPLENS_NUMA=1 bash artifact/run.sh overhead --profile paper --out artifact/results/cr-stock-overhead
```

Output: `artifact/results/cr-stock-overhead/summary.json`, plus trial results,
commands, binaries and compressed traces. The October 1 stock-logger reference
has ten runs per arm and update rate: EFRB **2.75% / 11.81%**, DVY **0.045% /
4.96%**, BCCO **−0.62% / 0.45%**, for 20% / 100% updates respectively. Overhead
is `100 * (1 - mean(logging) / mean(baseline))`. Negative values here do not
establish a benefit. The full procedure needs at least 100 GiB disk; storage
speed affects the result. See the [stock logger protocol and version boundary](../REPRODUCTION_CONFIGURATIONS.md#reproduce-logging-overhead-c2).

The older stock campaign's 60 raw compressed traces were removed with author
authorization after its audit; size/hash/event metadata and results remain.
This does not describe the [separate 400-cell headline campaign](../headline-pmu/README.md),
whose retained archives and logger/wait/PMU protocol have their own inventory
and reproduction commands. HSL's native rate, reader-only rate and writer
completion time remain separate metrics. No rerun is needed to inspect either
set of saved summaries.

## Version and validation boundaries

Frozen backend/UI sources represent the September 29 measurements; the sampling
sources represent the September 30 study. Their hashes are in `manifest.json`.
Running them reproduces the measured implementations, and does not by itself
revalidate timings on subsequently merged source. Application commands use the
current artifact with the recorded workload and corrected diagnostics. Preserve
their new provenance with any reported numbers.

The packaged component checks, saved-result arithmetic and controller failure
tests have been run. Full newly packaged browser, sampling and backend campaigns
have not all been rerun end to end. Saved results are the completed historical
measurements. Main-figure full-profile reruns and the separate perf-c2c input
example are deferred; the existing figure commands remain available.
