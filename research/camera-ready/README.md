# Camera-ready sampling work

The completed [local pipeline ablation](LOCAL_PIPELINE_ABLATION_RESULTS.md)
separates native conversion, backend preparation, actual database-to-UI loading,
and exact 64-KiB detail interactions. It includes both gains and negative results.

The [matched backend matrix](BACKEND_MATRIX_RESULTS.md) isolates spatial range
updates and temporal prefix sums under one configuration. The linked result
documents include configurations, measurements, and interpretation. Paper sources
and publication tables are distributed separately and are not part of this artifact.

This work is isolated on `codex/camera-ready-sampling`. On September 30,
the local CR work was checkpointed at `6e2052c`, then evaluator fixes through
`fe4c12d` were merged into this branch. The integration does not modify
evaluator-facing `main`. Earlier result files retain the sources and settings
they measured; merging fixes does not retroactively validate those measurements
against the integrated revision.

## Initial sampling versus representative selection

The converter uses `p` for random page retention, then adds pages to satisfy
the `s`-page floor per type (or all available pages when fewer than `s` exist).
Perf-directed pages are also retained. These steps determine the database
available to clustering, and are not limited by the GUI page/record budgets.
Only afterward does the GUI cluster those pages and run the selection policy
below. Its missing-type pass is budget-limited one-page coverage, not the
converter's `s` parameter. Thus `p=1` retains all pages and renders `s`
ineffective; varying `s` is informative when `p<1`.

The final sampling matrix must pass the CR budgets explicitly when calling
the backend outside the GUI. Final HNSW attribution is to be measured on Pyke
at both 128 D and 1536 D with the final workload and source settings, including
separation/alignment attribution. Earlier 768-D or other-host decompositions
are not substitutes. Before reusing other measurements, compare their source,
build, workload, allocator, placement, and measurement manifests against this
integrated branch; rerun affected comparisons with all variants together.

Integration checks (September 30): the Python suite reported 109 tests with
one SetBench-dependent class skipped because that submodule is absent from
this worktree. Continuation, current-bucket, detail-filtering, and snapshot-export
helper suites passed, including 2,649 current-bucket equality cases and 600
randomized detail-filter oracle checks. Comparing frontend source diagnostics
against checkpoint `6e2052c` found 51 on both sides and no added diagnostics;
this does not claim a clean production build. Full GUI interaction checks and
the final measurement campaigns have not been repeated on this merged revision.

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

The detail renderer also filters histories to the selected address region before
creating components, preserving enclosing objects, lifetime endpoints, and
expanded fields. See [DETAIL_OPTIMIZATION_RESULTS.md](DETAIL_OPTIMIZATION_RESULTS.md)
for paired dense-page timings and visual-equivalence checks. This is not viewport
virtualization; selecting an entire dense page can still be expensive.

The [staged ablation protocol](STAGED_ABLATION_PROTOCOL.md) contains draft paper
text for that optimization and a bounded plan for separately evaluating native
database construction, database-to-UI loading, and individual UI interactions.
It distinguishes equal-output prefix-sum comparisons from display-history
reduction, which changes retained detail. Additional measurements in that plan
are not yet run; [the earlier compact plan](PROCESSING_ABLATION_PLAN.md) is retained.

A [Pyke UI smoke](PYKE_UI_SMOKE.md) confirms that its installed Chromium can run
the optimized interface headlessly with software rendering. It records the
graphics difference from the local GPU-backed browser and single-trial latency
checks; it is not a completed processing ablation or repeated UI comparison.

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

The [event-schema comparison](EVENT_SCHEMA_RESULTS.md) records file/type lookup
normalization, original-size metadata, page-continuation markers, and measured
join/read costs on retained Valkey and BCCO databases.
