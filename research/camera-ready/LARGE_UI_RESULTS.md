# Large-history UI loading and interaction measurements

Follow-up: selected-region filtering is now implemented and measured in
[DETAIL_OPTIMIZATION_RESULTS.md](DETAIL_OPTIMIZATION_RESULTS.md). The measurements
below preserve the pre-optimization snapshot and the bottleneck that motivated it.

Measured September 28, 2026 (September 29 UTC), on the camera-ready branch.
Runtime: `0cdccc03f8b7b6c7419e803a9ac8c14f5a82391a`. No production source or
evaluator-facing branch was changed for this study.

## Outcome

The huge-page overview loads around one million prepared records in roughly two
seconds in this local test. Dense-page detail selection is a different story:
one fully packed 2-MiB page, with only 65,536 records, takes 18.6 seconds to select
a small region. This page fits under the GUI's 100,000-record default budget.
That budget bounds retained history size but does not guarantee responsive
drill-down. Per-page live-object count and mounted page count also matter.

These are browser loading/interaction measurements, **not database loading or
end-to-end trace preparation times**. Prepared synthetic page histories were
served through ordinary HTTP. The cache/statistics panels were fixed controls
from the retained BCCO fixture, not recomputed summaries of the synthetic objects.
The fixtures deliberately bypass page selection and the record cap. They test
frontend costs, not whether the sampler would normally select these payloads.

## Loading and detail selection

Three fresh-browser trials per case; table entries are medians. All pages are
2 MiB. Live fixtures contain nonoverlapping 32-byte objects that remain live.
The churn fixture has ten successive, nonoverlapping lifetimes per address, with
80% duty cycle; roughly one tenth of its records are live at the tested times.

| Prepared history records | Pages | Maximum records/page | Navigation to ready | Slider response | Small-region detail selection |
|---|---:|---:|---:|---:|---:|
| 100,000 live | 128 | 782 | 1.32 s | 108 ms | 0.70 s |
| 250,000 live | 128 | 1,954 | 1.56 s | 116 ms | 0.56 s |
| 1,000,000 live | 128 | 7,813 | 1.95 s | 127 ms | 1.53 s |
| 1,000,000 with address reuse | 128 | 7,813 | 1.97 s | 132 ms | 0.77 s |
| 1,048,576 live, fully packed | 16 | 65,536 | 1.64 s | 53 ms | 23.72 s |
| 65,536 live, fully packed | 1 | 65,536 | 0.99 s | 22 ms | 18.60 s |

Slider values are the median of the three within-trial medians. The corresponding
within-trial 95th-percentile medians are 122, 125, 140, 143, 61, and 28 ms in table
order. Each trial contains 30 commanded slider moves across three drags plus
three pointer-positioning moves; all 33 captured pointer-move events are retained.
These are input-handler-entry to second-animation-frame timings, not displayed
frame rate, compositor-present latency, or a guarantee of smooth dragging.

The region-selection gesture is named `brush-64k` in the harness. Its nominal
1/32-page span resolves to **68 KiB** with this viewport and 4-KiB selection
rounding, verified by the detail grid in the default-heap control. All main
trials produced the same brush width at the same starting page/address.
Selection timing uses pointer release through the second animation-frame
callback; it excludes the preceding short drag.

Trial-to-trial variation should remain visible: million-live/128-page selection
took 1.50, 1.53, and 3.06 seconds. Single dense-page selection ranged from 18.21
to 20.28 seconds; the 16-dense-page fixture ranged from 23.24 to 23.76 seconds.
Do not infer a monotonic performance curve from the small differences among
100k, 250k, and churn fixtures.

## Other interactions

Median response proxies, in milliseconds:

| Fixture | Page visibility | Cache visibility | Type filter/clear | Wheel scrolling | Zoom in | Zoom out |
|---|---:|---:|---:|---:|---:|---:|
| 100k / 128 pages | 336 | 255 | 65 | 17 | 39 | 617 |
| 250k / 128 pages | 275 | 144 | 38 | 16 | 28 | 335 |
| 1M / 128 pages | 267 | 144 | 54 | 16 | 98 | 354 |
| 1M reused / 128 pages | 478 | 253 | 67 | 17 | 39 | 695 |
| 1M / 16 dense pages | 89 | 52 | 34 | 16 | 1,176 | 192 |
| 65,536 / one dense page | 45 | 38 | 37 | 17 | 938 | 28 |

Zoom-in follows the expensive detail-selection action; its smaller value does
not replace or include that prior cost. The one-page view has little to scroll,
so its wheel response is only an event-response check. These trials did not
measure every tooltip, full-page selection, or every possible type-field layout.

## Why dense detail is expensive

The overview always draws 128 summary slots per huge page. The initial document
contains 19,975 elements for 128 pages, 3,623 for 16, and 1,433 for one. Fewer rows
therefore reduce overview work even when each page holds many more objects.

In `pagesComponent.tsx`, `ObjectLayout` maps the selected page's entire history
to components. `HoverableSplitBlock` checks time and type visibility but does not
reject objects outside the selected address range. SVG clipping hides those
objects without avoiding their component construction. Selecting the small
region in a dense page produced 65,536 object rectangles, plus two clipping
rectangles; the 16-page document grew to 266,984 elements.

The browser's sampled JavaScript heap reached about 1.9 GiB during dense-detail
actions. This is a post-action heap observation, **not peak RSS or a count of
live useful data**. The main trials used a protective 2,048-MiB V8 old-space
limit; that setting is not a total-browser-memory limit. To check this confound,
one additional fresh-browser trial used the browser's default heap setting:
the single dense page loaded in 1.00 s and its small-region selection still took
16.66 s, with 1,890.6 MiB of sampled JavaScript heap immediately afterward.
This single control confirms the delay persists without the explicit cap; it
does not quantify a heap-limit speedup.

A narrow next optimization is to filter by lifetime, visibility, and **interval
intersection with the selected region before constructing detail components**.
Objects crossing region boundaries and nested containers must remain included.
That change has not been implemented or benchmarked. The present evidence
identifies a source-supported candidate, not a measured causal speedup.

## Protocol and scope

- Local Intel Core i7-14700KF Windows host; headless Edge/Chromium 154.0.4258.37,
  1440x1000 viewport, separate browser process/profile per trial.
- Artifact Next.js development server in WSL2 Docker, four CPUs and 8 GiB;
  fixture server two CPUs and 4 GiB. Browser execution is on Windows. This is a
  local developer-host test, not a dedicated hardware scalability study or a
  production-build benchmark.
- The disposable UI copy differs from the branch only in selecting a 2-MiB
  initial view for these fixture names, plus whitespace. The page-rendering
  source hash matches the branch. No runtime optimization was made this turn.
- Route compilation was warmed before collection. Every measured browser used
  normal HTTP, fresh context/cache, and no intercepted/mock network responses.
  Navigation-to-ready includes transfer, JSON decoding, initialization and
  initial rendering, but excludes database preparation and fixture generation.
- The fixed non-page payload is substantial: total uncompressed JSON ranges
  from 67,559,263 bytes (one dense page) to 210,393,315 bytes (million-record
  churn). Therefore these are not timings for decoding only the event arrays.
- Each trial drags to 25%, 50%, and 75% of the time range, toggles page and cache
  visibility twice, filters/clears types, scrolls, brushes a region, and zooms
  in/out. Assertions check page count, changed slider position, nonempty brush,
  populated detail, and zoom state. All 18 main trials and the one default-heap
  control completed without uncaught page errors or automatic exports.
- The first exploratory batch exposed a Windows browser-cleanup problem.
  It is excluded from these tables. The final batch verified termination of
  each launched browser tree before the next trial; its 18 cleanup records match
  its 18 completed trials. Both local test servers were stopped afterward.

## Evidence and replay

- [Main summary, including per-trial observations](large-ui-results-20260928.json).
- [Single default-heap control](large-ui-default-heap-20260928.json).
- Author-workspace raw logs and screenshots:
  `artifact-tools/large-ui-stress-20260928/isolated-complete/` and
  `artifact-tools/large-ui-stress-20260928/default-heap-control/`.
  Other sibling folders contain discarded pilots, not table inputs.
- Fixture sizes and SHA-256 hashes are in that evidence root's `manifest.json`
  and `manifest-dense64k.json`. Generated payloads remain in the disposable WSL
  directory `/tmp/heaplens-large-ui-20260928-fixtures`; they are not added to Git.
- `serve_large_ui_fixtures.py --prepare` builds fixtures from the retained
  common/page payloads mounted at `/author-tools`. Run it without `--prepare`
  to serve `/fixtures` on loopback port 5000. The disposable UI uses port 3001.
- `benchmark_large_ui.cjs` takes `HEAPLENS_PLAYWRIGHT`, `HEAPLENS_BROWSER`, and
  `HEAPLENS_EVIDENCE`. For the main protocol set `HEAPLENS_REPS=3`,
  `HEAPLENS_CASES=["dense64k","live100k","live250k","live1m","churn1m","dense1m"]`.
  Order reverses on alternate repetitions. Set `HEAPLENS_WARMUP=0` only after
  warming the route separately. Default heap limit is 2048 MiB; use
  `HEAPLENS_JS_HEAP_MB=default` for the default-limit control. Windows needs permission
  to terminate the exact browser PID returned by the launcher after each trial.
- `summarize_large_ui.cjs RAW_BROWSER_JSONL OUTPUT_JSON` regenerates summaries.
  Its aggregate p95 values are descriptive within-trial percentiles, not
  confidence bounds from three trials.

For paper positioning and proposed equal-output experiments, see
[the compact processing-ablation plan](PROCESSING_ABLATION_PLAN.md). These UI
stress observations alone do not establish the speedup of any optimization.
