# Camera-ready sampling work

This work is isolated on `codex/camera-ready-sampling`, based on evaluator
revision `8b67cade6017ac8e3ccff242a208c5dc025380ea`. The evaluator-facing `main`
branch and its checkout are unchanged. No native converter or benchmark
configuration changes are included.

## Selection policy

Keep mandatory perf-directed pages; count them toward the normal page budget,
and report explicitly if they alone exceed it. Then:

1. In shuffled cluster order, choose a page from each still-unrepresented
   cluster until the budget is reached.
2. Use remaining slots for requested types not yet represented in the prepared
   page histories. A page may satisfy several missing types.
3. Use remaining slots for additional page runs, respecting the existing run
   controls and checking the distinct-page count after each addition.

The first two passes take precedence over the run controls. The default budget
formula remains unchanged (52 at 4 KiB, 17 at 2 MiB); an optional backend
`page_budget` argument supports controlled analysis without editing a constant.
No new GUI budget control is claimed. Selection metadata reports omitted
clusters/types and any mandatory-perf exception. Coverage applies to types
present in prepared histories, not to every type at every timestamp.

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
