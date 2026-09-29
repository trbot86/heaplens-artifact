# Camera-ready sampling work

This work is isolated on `codex/camera-ready-sampling`, based on evaluator
revision `8b67cade6017ac8e3ccff242a208c5dc025380ea`. The evaluator-facing `main`
branch and its checkout are unchanged. No native converter or benchmark
configuration changes are included.

## Selection policy

Keep mandatory perf-directed pages; count them toward the normal page budget,
and report explicitly if they alone exceed it. Then:

1. In shuffled cluster order, choose a page from each still-unrepresented
   cluster within both budgets. Prefer a page near the cluster's median
   history size; when full cluster coverage is feasible, reserve enough
   records for at least the cheapest member of every remaining cluster.
2. Use remaining slots for requested types not yet represented in the prepared
   page histories. A page may satisfy several missing types.
3. If a cluster's largest history has at least four times as many records as
   its smallest (using one as the denominator for an empty history), try to
   include both extremes. This is a history-size heuristic, not a peak-live
   density or churn classification; types and clusters take precedence.
4. Use remaining slots for additional page runs, respecting the existing run
   controls and checking the distinct-page count after each addition.

The GUI defaults are now 128 pages and 100,000 prepared history records, with
both controls in Sample settings. The response and visible status report
omitted clusters/types, uncovered history extremes, and mandatory-perf
exceptions to either limit. Coverage applies to types present in prepared
histories, not to every type at every timestamp. The cap is applied after
reconstruction/clustering; it cannot bound full-database or cache preparation.

Direct Python callers retain the earlier 52/17 page formula and page-only
selection unless they pass `page_budget` and `record_budget`. In particular,
the separate CLI LLM exporter has not adopted the GUI defaults or its new
five-snapshot protocol. Earlier comparison scripts remain reproducible.

See [HISTORY_BUDGET_RESULTS.md](HISTORY_BUDGET_RESULTS.md) for the coverage sweep,
stress tests, and remaining limits. The GUI text exporter is now on demand,
incremental, cancellable, and isolated from page-row progress rerenders.

Perf treatment remains compatible pending the author's choice about whether
the budget should also cap mandatory perf-directed pages. Sampling-study
inputs without forced perf pages do not depend on that choice.

## Evaluation boundary

Compare frozen baseline and branch selectors on the same prepared pages and
cluster assignments, across the existing 20-seed trace matrix. Score the
previously verified genuine rare raxNode identities, not a relaxed replacement
predicate. Keep the separate lifetime-ordering issue unchanged in this study.

The narrow cache-range and selected-bucket optimizations are now integrated,
with equal-output checks and paired browser tests. No backend result cache,
row virtualization, or cache-format change is included. See
[OPTIMIZATION_RESULTS.md](OPTIMIZATION_RESULTS.md) for measured gains and limits.

## Findings and reproduction

See [RESULTS.md](RESULTS.md) for the selection comparison, remaining capacity
limits, tested acceleration opportunities, and validation scope. Compact
machine-readable results are in [results-20260928.json](results-20260928.json).
Large input databases, replay payloads, profiles, and per-trial logs remain in
the author workspace, outside this branch's tracked files.

The research scripts use the pinned artifact Python environment. They are not
part of `artifact/run.sh` or a change to the performance-reproduction protocol.

- `compare_selection.py`: paired selector comparison; `--help` lists input
  paths, frozen baseline root, prior study results, and rare-layout oracle.
- `profile_preparation.py`: profile baseline preparation, including database,
  page, cache, and encoding phases; `--help` lists arguments.
- `benchmark_cache_updates.py`: offline cache-accumulation prototype and
  complete-output comparison. Mount the frozen baseline at `/baseline`.
- `benchmark_ui_calculations.cjs`: offline Node benchmark and every-bucket
  equality checks. Mount baseline source at `/baseline`, earlier replay
  fixtures at `/prior`, and an output directory at `/evidence`; TypeScript
  comes from `/opt/heaplens-ui/node_modules` in the artifact image.
- `summarize_results.py WORKSPACE --out FILE`: derive the compact result file
  from retained raw measurements. Uses ordinary medians, including averaging
  the middle two observations for even-sized samples.

From the repository root, run the selector and existing cache regressions with
`python3 -m unittest artifact.tests.test_representative_selection artifact.tests.test_cache_limits`.
The wider regression command is `python3 -m unittest discover -s artifact/tests`.
