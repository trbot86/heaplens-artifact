# Selected-region detail rendering

Preserved earlier 68-KiB measurements. For fresh paired trials with the brush
verified at exactly 64 KiB, see [the local ablation report](LOCAL_PIPELINE_ABLATION_RESULTS.md).

September 29, 2026. Implemented locally on `codex/camera-ready-sampling`.
Evaluator-facing `main` is unchanged. No sampling, reconstruction, database,
benchmark-workload, cache-preparation, or exporter implementation is changed.

## Mechanism

Previously, `ObjectLayout` sorted the whole selected page's shared event array
and created a React component for every history record. Each component checked
liveness and type visibility; SVG clipping hid objects outside the inspected
region but did not avoid component creation.

`selectDetailEvents` now filters before sorting and component construction.
It uses interval intersection, retaining objects that enclose or cross the
selected region, and preserves the existing inclusive allocation/free endpoints.
It also retains a parent when an expanded field reaches the region even if the
stored parent fragment does not. Zero-sized allocation markers in the region
are preserved. Sorting is stable and operates on the filtered copy, so inspecting
a region no longer mutates the shared history array. All original records remain
available to other views and export; no data is discarded from the trace.

The helper is generic: it uses the selected address range, time, visibility, and
field metadata. It contains no workload names, fixed page sizes, test addresses,
page-count cutoffs, or special cases for the benchmark fixtures. Results are
memoized with all those inputs as dependencies.

## Fresh paired measurements

Three interleaved baseline/optimized trials per fixture. Both variants use the
browser's **default heap policy**, unlike the protective 2-GiB setting in the
earlier exploratory study. Compare these fresh pairs, not one of the earlier
baseline medians. Each trial has its own browser process; cleanup is verified.

The operation selects a 68-KiB region of a 2-MiB page. Objects are 32 bytes and
remain live. Entries below are medians of input-release to second-animation-frame
callback timings, a responsiveness proxy rather than compositor-present latency.

| Prepared histories / pages | Before | After | Speedup | Object rectangles before / after |
|---|---:|---:|---:|---:|
| 65,536 / one fully packed page | 12.05 s | 0.417 s | 28.9x | 65,536 / 2,176 |
| 1,048,576 / 16 fully packed pages | 21.91 s | 0.436 s | 50.3x | 65,536 / 2,176 |
| 1,000,000 / 128 pages | 3.12 s | 1.223 s | 2.55x | 7,813 / 2,176 |

Two additional clipping rectangles are present in raw `detailRects` counts.
The complete document after selection shrank from 264,793 to 14,553 elements
for the single dense page, and from 266,983 to 16,743 for 16 dense pages.

Maximum **post-selection sampled JavaScript heap** across the three trials:

| Fixture | Before | After |
|---|---:|---:|
| One dense page | 1,969.5 MiB | 270.9 MiB |
| 16 dense pages | 2,030.4 MiB | 328.1 MiB |
| 128 pages | 581.0 MiB | 417.7 MiB |

These are sampled heap observations, including garbage awaiting collection, not
peak process RSS or a measurement of retained live data alone. No forced garbage
collection was used.

Variability is retained in the raw results. Single-dense-page baseline trials
were 11.14, 20.18, and 12.05 seconds; optimized trials were 0.400, 0.417, and
0.417 seconds. The 16-page optimized trials were 0.435, 0.436, and 0.720 seconds.
Do not treat three trials as a universal latency bound.

Loading and overview behavior were not the target: median navigation-to-ready
was 1.20/1.19 seconds for one page, 1.77/1.84 for 16, and 2.06/1.89 for 128
(before/after). These small differences do not establish a loading optimization.
The 128-page selection remains slower because avoiding irrelevant detail
components does not eliminate work on all mounted page rows.

## Correctness and regression checks

- The new helper passes strict TypeScript checking, 600 randomized comparisons
  against an independently expressed interval-clipping oracle, and explicit
  tests for left/right boundary crossings, enclosing/nested objects, address
  reuse, exact allocation/free endpoints, hidden/null types, zero-size markers,
  empty regions, expanded fields, stable ordering, and immutable input.
- The dense input selects exactly 2,048 records for a 64-KiB interval and all
  65,536 for the entire 2-MiB page. There is no hidden record cap.
- Baseline and optimized browsers matched **16 detail screenshot pairs pixel
  for pixel**, their corresponding cache-state hashes, and two object tooltips.
  Inputs were a retained Valkey page containing `raxNode` objects and a synthetic
  nested huge-page layout with enclosing regions, boundary-crossing objects,
  fields, and reused addresses. The latter uses retained BCCO panels as fixed
  controls and is not presented as an application trace.
- Browser checks exercise detail selection, detail zoom/pan, field expansion,
  type hiding/restoration, a later time, object tooltips, and huge-page zoom in/out.
  There were no uncaught page errors. All 18 performance trials also completed
  without page errors and recorded verified cleanup.
- Existing selected-bucket UI checks pass: 2,649 equal-output cases. Existing
  snapshot-export checks pass, including the million-record stress, cooperative
  yielding, cancellation, write failure, Unicode, and bounded download fallback.
- Full frontend source checking reports the same 51 pre-existing diagnostics
  for baseline and candidate, with no added diagnostic expressions. This is not
  a claim that the deferred production-build typing cleanup is complete.

The earliest visual-test attempts were discarded because the harness obtained a
layout box from an SVG clip definition, which is not an ordinarily rendered
element. The final harness tests tooltips at the known-live selection time and
transforms declared clip coordinates into screen coordinates. Final evidence is in
`correctness-verified`, not the earlier attempt directories.

## Scope and remaining limits

This is selected-region filtering, **not viewport virtualization**. Selecting a
whole dense page still retains all its live objects, and even the selected region
can contain many objects or fields. The detail grid also continues to create
ticks for the selected range. Large full-page views and all-row updates remain
separate optimization opportunities. Selection budgets and retained histories
are unchanged.

The removed in-place sort previously let a detail interaction reorder the shared
array. Export code and contents are unchanged; exported record ordering can now
remain in its input order rather than inherit that incidental interaction-driven
sort. The helper's nonmutation checks cover this boundary.

## Environment, evidence, and replay

- Local Intel Core i7-14700KF Windows host, headless Edge 154.0.4258.37,
  1440x1000 viewport; artifact Next.js development UI in WSL2 Docker. Each UI
  container has four CPUs and 8 GiB. The ordinary-HTTP fixture server has two
  CPUs and 4 GiB. Database preparation is excluded; inputs and palettes are fixed.
- Baseline revision: `0cdccc03f8b7b6c7419e803a9ac8c14f5a82391a`.
  Both disposable UIs use the same test-only 2-MiB initial setting. The candidate
  differs only by `detailEvents.ts` and its integration in `pagesComponent.tsx`.
- Tested/local `pagesComponent.tsx` SHA-256:
  `e8af9d952ff0767e563a9e251384d2d6b86e2ea5d774b4993b81cee92b1550ca`.
  `detailEvents.ts` SHA-256:
  `f810fc97219fd9b262ecc093e39eec01db49f22c06fc9b0fad1017f280c80d60`.
- [Machine-readable paired results](detail-ablation-results-20260929.json).
  Raw trials, cleanup records, screenshots, and visual comparisons are in the
  author workspace's `artifact-tools/detail-ablation-20260929/`.
- Disposable copies remain at `/tmp/heaplens-detail-ui-20260929/{baseline,candidate}`.
  The baseline/candidate UI ports are 3002/3003; the fixture service uses 5000.
  The existing generated fixtures and hashes are documented in
  [the initial large-input report](LARGE_UI_RESULTS.md).
- `run_detail_ablation.cjs` runs the paired protocol using
  `HEAPLENS_PLAYWRIGHT`, `HEAPLENS_BROWSER`, and `HEAPLENS_EVIDENCE`.
  `summarize_detail_ablation.cjs EVIDENCE OUTPUT_JSON` regenerates the report data.
- `check_detail_browser.cjs` additionally uses `HEAPLENS_FIXTURE_ROOT` for the
  author-workspace fixture directory. It tests rendered equivalence separately
  from timings. Both UI servers and the fixture server were stopped afterward.
- `node artifact/tests/test_detail_events.cjs` runs the pure helper checks in
  the artifact's pinned UI dependency environment.

This supplies a concrete UI engineering ablation: avoiding construction of
irrelevant detail components improves response time while preserving the tested
visible results. It does not measure the proposed backend prefix-sum ablation or
establish novelty of interval filtering itself.
