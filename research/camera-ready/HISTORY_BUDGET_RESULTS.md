# Page/history budgets and on-demand export

Implemented only on `codex/camera-ready-sampling`, after `d97bf5e`. Evaluator
`main`, native instrumentation, converter sampling, benchmark settings, and the
separate CLI LLM export protocol are unchanged.

## Selection policy

The GUI now defaults to 128 representative pages and 100,000 **prepared history
records**. Both limits are editable under Sample settings and apply on Resample.
These records can include successive allocations at one address and prepared
fragments; the count is not peak live-object count or raw log-event count.

In shuffled cluster order, prefer a page near the cluster's median history
count. When one page per cluster fits both budgets, reserve the minimum cost
of each remaining unrepresented cluster before choosing the current page.
This prevents a needlessly expensive representative from displacing another
cluster. Otherwise, preserve shuffled cluster order and report omissions;
do not sort clusters from cheapest to most expensive.

Next cover missing requested types. With remaining capacity, try to include
the minimum- and maximum-history pages of clusters whose counts span at least
4x, then add consecutive runs. The 4x threshold is an explicit heuristic, not
an experimentally optimized threshold or a new fingerprint dimension. This
does not yet distinguish many simultaneously live objects from high churn.

Mandatory perf-directed pages retain their existing exception to the budgets.
The response records both overages; the UI warns about them, omitted clusters,
and missing types, and reports history-count extremes it could not include.
Ordinary selection never exceeds either budget.

The limits constrain selected-page transfer and interaction work. They cannot
bound reconstruction, clustering, full-database cache preparation, string/field
metadata size, or every zoomed-detail rendering cost. Source traces are retained.
Direct Python callers retain the previous page-only defaults unless they pass
the new limits; in particular the CLI LLM exporter is unchanged.

## Retained-input coverage

Seven retained views, 20 clustering/selection seeds each, 128-page cap; four
record-budget configurations (none, 25,000, 50,000, 100,000): **560 selections**.
Clustering inputs and seeds are shared across the compared policies; this
changes representative selection, not the fingerprint or initial log sampling.

- At 100,000 records, all clusters and requested types are represented in
  **140/140 trials**. The previously audited genuine rare Valkey `raxNode`
  identities survive in **20/20** trials.
- At 25,000 records, the BCCO 2-MiB view selects **82–100 pages**, rather than
  128, while retaining all clusters and types in **20/20** trials. All seven
  views retain cluster/type coverage in this sweep at that limit as well.
- With the 100,000 cap, the BCCO 2-MiB view uses at most **45,047 records**;
  the full Valkey view at most **9,605**. Thus the larger default leaves
  headroom; these retained traces do not establish an optimal limit.
- A regression with 128 distinct clusters, each containing a 2-MiB page packed
  with 65,536 32-byte objects, selects one page under the 100,000-record cap and
  explicitly reports 127 omitted clusters. It cannot silently admit 8,388,608
  records just because the page cap is 128.

The huge-page retained fixture groups a previously 4-KiB-sampled database.
It is not evidence that arbitrary dense huge-page traces have the same cost.
The known-anomaly result remains trace-specific, not a general recall claim.

## Browser stress measurements

Synthetic histories replace the selected pages' events in the real BCCO
payload, keeping 128 two-MiB rows and the cache/statistics payload fixed. One
variant keeps all synthetic records live; the other cycles through short
lifetimes. These are UI workload stresses, not application measurements or
physically reconstructed database traces. Three trials per row below, local
headless Edge 154.0.4258.37, 1440x1000 viewport, warm Next development server:

| Prepared records | Lifetime pattern | Ready, median | Slider response proxy, median |
|---:|---|---:|---:|
| 50,000 | All live | 1.990 s | 112.0 ms |
| 50,000 | Short-lived | 1.961 s | 106.5 ms |
| 100,000 | All live | 2.077 s | 112.9 ms |
| 100,000 | Short-lived | 2.124 s | 112.2 ms |

The response proxy is input-handler entry to the second animation frame, not
paint latency or FPS. These runs use Playwright response replay. A larger
250,000-record response stalled that mocked-response path. Repeating the live
case over ordinary loopback HTTP completed normally: one trial, 1.732 s ready,
117.2 ms slider proxy, no page errors. Its loading time is not directly
comparable to the replay rows. The stall is not counted as an application
failure or a successful replay trial; its precise test-transport cause is not
established. The record cap was intentionally bypassed to run these stresses.

100,000 is a conservative, adjustable working default, **not a measured
performance cliff**. Dense full-page zoom, very large type metadata, slower
machines, and mandatory-perf overflow still need separate consideration.

## Export changes and checks

- Replace the automatic load-time download with **Export 5 snapshots**.
- Stream output to a user-selected file where the browser supports it; other
  browsers use a 64-MiB-limited Blob download. Oversized fallback exports fail
  visibly rather than producing silently truncated files.
- Compute timestamp bounds by scanning instead of flattening/spreading the
  entire history into function arguments. Use one byte per record for its
  snapshot visibility mask, rather than repeated arrays of visible objects.
- Emit bounded text chunks and yield cooperatively for progress/cancellation.
  Export progress is local to its control and does not rerender every page row.
- Preserve the text format, object order, inclusive free-time boundary, and
  allocation-timestamp range. Five snapshots replace nine; empty histories
  produce one empty snapshot. Correctly read nested `page_num` cluster lists
  without mutating input arrays.

Validation includes byte-for-byte comparison with the prior serializer after
changing its interval count to four, empty/constant/boundary cases, Unicode
chunk boundaries, a million-record history that triggers the former spread
failure, cooperative yielding, cancellation, sink failure, fallback size
limits, and both cluster-list shapes. Browser checks on retained Valkey and
BCCO views confirm no automatic download, five-snapshot download, cancellation
with a deliberately slow sink, a simulated direct-file sink, and settings
propagation. Native save-dialog/OS-file handling is not automated by these
tests. Screenshots were inspected for the updated controls and coverage status.
An empty representative selection also renders normally, reports omitted
coverage, and disables export. The final Python run reports 94 tests with one
existing skip; the unchanged UI math suite checks 2,649 synthetic cases.

The frontend's existing production-build/type-check problems were not cleaned
up: 51 source diagnostics remain, with no new code/expression diagnostics.
The standalone exporter and current-bucket helpers pass their strict checks.

## Evidence

[Compact results](history-budget-results-20260928.json) are generated by
`summarize_history_budget.py EVIDENCE --out FILE`. Raw cases, browser event logs,
and screenshots are in the author workspace's
`artifact-tools/history-budget-20260928/`, not shipped trace payloads.

- `evaluate_history_budget.py --help`: retained-input selection sweep.
- `check_history_budget_browser.cjs`: set `HEAPLENS_PLAYWRIGHT`,
  `HEAPLENS_BROWSER`, and `HEAPLENS_EVIDENCE`; optional `HEAPLENS_CASES` and
  `HEAPLENS_REPS` select runs. `HEAPLENS_USE_HTTP=1` bypasses response mocking;
  `serve_history_stress.py` supplies the 250,000-record HTTP cross-check.
- `python3 -m unittest discover -s artifact/tests`: Python regressions.
- `node artifact/tests/test_snapshot_export.cjs`: exporter checks in the pinned
  artifact image; `HEAPLENS_BASELINE` enables prior-serializer comparison.
- `node artifact/tests/test_current_bucket.cjs`: unchanged UI math checks.
- `check_frontend_diagnostics.cjs OLD_UI NEW_UI`: compare known source errors
  by diagnostic code and offending expression, without a broad refactor.
