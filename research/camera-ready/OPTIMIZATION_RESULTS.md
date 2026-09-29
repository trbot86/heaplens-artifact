# Integrated loading and UI optimizations

September 28, 2026. Changes are isolated on `codex/camera-ready-sampling`.
The comparison baseline is commit `e45d924`, which already contains cluster-first
selection. Evaluator-facing `main`, default page budgets, application benchmark
configurations, native conversion, and lifetime reconstruction are unchanged.

## Changes and outcome

Two narrow optimizations are now integrated:

1. Cache preparation accumulates each object's cache-line contributions using
   scalar/range updates, instead of allocating repeated-index arrays for
   `np.add.at`. Whole cycles through the cache sets preserve multiplicities.
2. Huge-page slot summaries and cache visible-type totals are computed for the
   selected time bucket, rather than building all 2,002 buckets on visibility
   changes. Cache-tooltip percentages and colour-scale bounds use those same
   selected-bucket totals. Debug logging in the replaced cache aggregation was
   also removed.

Preparation and visibility toggles improved substantially. Larger-view slider
responsiveness did not materially improve: the remaining all-row rendering and
update work is a separate target. No persistent backend cache, row virtualization,
dependency upgrade, production-build cleanup, or data-format change is included.

## Backend preparation

Three fresh-Sampler trials per implementation/input, interleaved baseline/optimized,
optimized/baseline, baseline/optimized. Each resets the clustering/selection seeds
and runs database loading, statistics, page preparation, L1 cache preparation,
and compact JSON encoding. The complete JSON payload hash was identical across
all six trials for each input. Times exclude HTTP delivery and browser work.

| Retained trace | Baseline total, median | Optimized total, median | Reduction | Cache phase, baseline / optimized |
|---|---:|---:|---:|---:|
| Full Valkey, 52 pages | 11.90 s | 8.70 s | 26.9% | 6.83 / 3.56 s |
| BCCO, 17 huge-page representatives | 27.20 s | 12.04 s | 55.7% | 22.24 / 7.09 s |

Database reading itself was not changed. These are warm local postprocessing
measurements, not cold-storage or Jax/Pyke application measurements. Backend
containers used two CPUs, 12 GiB, and one BLAS/OpenMP thread on the local
Intel Core i7-14700KF/WSL2 host, with the pinned artifact Python environment.

## Browser measurements

Both versions received identical saved cluster-first payloads, fixed saved
colour palettes, and a 1280x720 viewport. Separate disposable copies ran the
artifact's Next.js development server. A separate headless Edge/Chromium
154.0.4258.37 browser exercised normal mouse/keyboard interactions through
Playwright. Each condition had three fresh-context trials, with execution order
alternated. Both frontend versions were warmed before collection to exclude
first route compilation. Backend preparation was excluded through payload replay.

The loading measure is navigation to the second animation-frame callback after
the panels are ready. Interaction measures are input-handler entry to a second
animation-frame callback: a responsiveness proxy, not compositor-present latency
or continuous-drag FPS. The table gives the median of the three trial medians.
Each trial contains sixty measured slider moves during three drags, two toggles
of each visibility checkbox, two filter changes, and one wheel action.

| View | Navigation to ready, baseline / optimized | Page visibility | Cache visibility | Slider dragging |
|---|---:|---:|---:|---:|
| Valkey, 52 pages | 1.720 / 1.237 s | 85.9 / 87.2 ms | 568.5 / 78.5 ms | 54.1 / 54.2 ms |
| BCCO, 17 huge pages | 1.592 / 1.142 s | 80.4 / 54.7 ms | 488.0 / 52.1 ms | 28.7 / 29.0 ms |
| BCCO, 128 huge pages | 2.140 / 1.509 s | 446.0 / 226.8 ms | 570.6 / 136.5 ms | 108.3 / 109.4 ms |

These drags visit 90%, 50%, and 90% of the time range; visibility toggles occur
at 90%. A separate three-pair BCCO-128 sequence visits 25%, 35%, and 30%, during
the allocation-heavy interval. It corroborated the result: page toggles
444.3 / 226.1 ms, cache toggles 574.0 / 136.2 ms, and slider dragging
107.3 / 108.6 ms. Thus the observed toggle gains are not confined to the late,
mostly reclaimed view.

Scrolling stayed around 16-17 ms in these checks. Filtering did not improve:
Valkey measured 29.9 / 37.7 ms, and BCCO-128 35.8 / 36.1 ms. These small-trial
observations do not establish a universal regression bound or a speedup for
every interaction. Do not add backend and browser medians and describe the sum
as a measured end-to-end loading latency.

At 128 BCCO rows the initial DOM still contains 19,949 elements. Computing just
the selected bucket avoids creating 32,800,768 huge-page slot cells on a
visibility change; the replacement contains 16,384 cells. These are derived
array-cell counts, not measurements of browser RSS. The unchanged slider cost
indicates that removing all-bucket arithmetic does not eliminate the costs of
updating all mounted rows.

## Correctness and integration checks

- Full Python regression discovery succeeded: 85 reported tests, with the
  unrelated allocator class skipped because this isolated worktree lacks its
  SetBench submodule. The four new cache-range tests cover wraparound, repeated
  sets, zero and negative counts, mixed signed updates, and integrated object,
  field, and free-event handling.
- The pure UI helper passes strict TypeScript checking and 2,649 synthetic
  equal-output cases. These include unusual histories with frees preceding
  allocations, preserving the previous arithmetic rather than silently fixing
  a different problem.
- Actual baseline helpers versus integrated helpers matched 74,826,752
  slot/cache-set values over every time bucket and two visibility masks in the
  retained fixtures, including the 128-page BCCO view.
- Twelve paired browser trials matched 132 recorded rendered-state signatures
  (row labels and SVG attributes, cache colours/counts, and slider position).
  Text exports matched after removing only the `GENERATED_AT` timestamp.
  No uncaught page errors occurred in these trials.
- Additional paired checks exercised field expansion, cache tooltip values and
  percentages, selecting a different Valkey page, and brushing a huge-page
  range. Their selected states and tooltips matched, without uncaught errors.
- Screenshots were retained for visual inspection. These checks do not replace
  exhaustive testing of every control/cache geometry. Existing production-build
  typing issues were not addressed through an unrelated refactor.

## Remaining opportunities

The 128-page view is more responsive, but a roughly 109 ms drag-response proxy
and 227 ms page-visibility toggle still leave room for improvement. Rendering
only visible rows, avoiding unnecessary React row updates, and separating
selected-page detail work from every-row updates are plausible next steps.
They need a separate profile and careful selection/scrolling/highlighting tests.
The current measurements do not identify an exact fraction attributable to each.

Reusing immutable backend results on page-only resampling could also eliminate
repeated database/cache preparation; it remains unimplemented. This requires
explicit invalidation and memory bounds, rather than caching mutable Samplers.

## Evidence and rerunning

- [Primary summary](optimization-results-20260928.json) and
  [allocation-heavy interval summary](optimization-active-results-20260928.json).
- `benchmark_integrated_backend.py` reads `/baseline` (frozen `e45d924`) and
  `/candidate`; pass a retained database, case name, page size, and output root.
- `summarize_integrated_optimization.py EVIDENCE --out FILE` derives the primary
  summary; add `--browser-prefix active-` for the second sequence.
- `benchmark_optimization_browser.cjs`, `optimization_ui_probe.js`, and
  `check_optimized_ui_features.cjs` contain the browser protocol. Set
  `HEAPLENS_PLAYWRIGHT` to the installed package path, `HEAPLENS_BROWSER` to the
  browser executable, and `HEAPLENS_EVIDENCE` to an existing output directory.
  The baseline/optimized UI copies use loopback ports 3000/3001, with the
  `optimization_ui_server.py` replay service on 5000. Its `/author-tools` mount
  supplies the retained fixtures. The test-copy preparer only supplies the
  2-MiB initial setting and dependency symlink; it does not edit source checkouts.
- For the allocation-heavy sequence set `HEAPLENS_STUDY_LABEL=active-`,
  `HEAPLENS_BROWSER_CASES=[["tpcc-bcco-2m",128,"itemid_t"]]`, and
  `HEAPLENS_SLIDER_POSITIONS=[0.25,0.35,0.3]`.
- `node artifact/tests/test_current_bucket.cjs` runs pure UI regressions in the
  pinned UI environment. Optional `HEAPLENS_BASELINE` and `HEAPLENS_FIXTURES`
  paths enable comparisons against frozen source and all retained time buckets.
- Raw logs, per-trial browser records, screenshots, and feature-check output are
  in the author workspace's `artifact-tools/integrated-optimization-20260928/`.
  Large inputs and replay payloads are not added to this branch.
