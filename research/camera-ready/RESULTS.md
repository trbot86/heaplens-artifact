# Cluster-first selection and loading opportunities

Author-side results, September 28, 2026. Work is isolated on
`codex/camera-ready-sampling`, based on evaluator commit
`8b67cade6017ac8e3ccff242a208c5dc025380ea`. No changes were pushed to a remote,
and evaluator-facing `main` was not changed.

## What changed

Representative selection now visits distinct clusters before spending spare
slots on missing types, and only then selects additional page runs. It counts
distinct pages and checks the budget after each addition. The 52-page (4-KiB)
and 17-page (2-MiB) defaults remain unchanged. Mandatory perf-directed pages
count toward the budget; if they alone exceed it, they remain included and
the response reports the exception. This preserves the existing forced-page
behavior pending a decision about a strict cap.

The response includes counts and lists of omitted clusters/types. The frontend
does not yet display this new metadata: this is not a claim that the interface
already warns about omissions or provides access to every omitted cluster.
Fingerprint construction, clustering, native sampling, lifetimes, and benchmark
configurations were not changed.

## Same-input comparison

Seven retained trace/view configurations, twenty seeds (20260928 through
20260947), two selectors, and three budgets produce 840 selections. Each
comparison reuses the same prepared pages and cluster assignments, with the
same starting selection seed for both policies. Clustering uses MiniBatchKMeans,
all types, the full time range, 2,000 buckets, 64-byte lines, and run controls
of three runs of up to five consecutive pages. The baseline defaults exactly
replayed the previous study's cluster/page counts in all 140 trials and the
rare-layout counts in all twenty full-Valkey trials.

Each table entry is the number of trials, out of twenty, covering **every
cluster / every eligible type** with the new selector. Type coverage means
presence in prepared page histories, not presence at every selected time.

| Retained input / view | Default budget | At default | At 64 pages | At 128 pages |
|---|---:|---:|---:|---:|
| Full Valkey, 4 KiB | 52 | 20 / 20 | 20 / 20 | 20 / 20 |
| Packaged Valkey, 4 KiB | 52 | 20 / 20 | 20 / 20 | 20 / 20 |
| HNSW Nasus diagnostic trace, 4 KiB | 52 | 20 / 20 | 20 / 20 | 20 / 20 |
| HNSW perf-c2c diagnostic trace, 4 KiB | 52 | 20 / 20 | 20 / 20 | 20 / 20 |
| Packaged illustrative EFRB trace, 4 KiB | 52 | 20 / 20 | 20 / 20 | 20 / 20 |
| BCCO-related trace, 4 KiB | 52 | 15 / 0 | 20 / 13 | 20 / 20 |
| Same BCCO-related trace, 2 MiB | 17 | 0 / 0 | 20 / 13 | 20 / 20 |

No new-policy trial exceeded its budget. The HNSW perf-c2c trace had three
mandatory pages; the other inputs had none. The mandatory-perf-overflow
exception is unit-tested, but was not exercised by these traces.

In full Valkey at budget 52, the established rare raxNode pattern survived in
**20/20 trials, versus 7/20 with the baseline selector**. There were 24–44 of the
54 verified live, small, cache-line-crossing objects in each new sample. The
oracle uses the same fixed timestamp, five target pages, and verified genuine
allocation identities as the previous analysis; stale lifetime identities do
not count. This is a computational check on the selected payload, not an LLM
judgment or a new human usability study. It does not establish arbitrary-anomaly
recall, and this comparison does not isolate the cluster pass from the type pass.

Capacity still matters. At the 17-page default, BCCO has 52–64 clusters and now
represents exactly seventeen, versus only 3–7 previously. At 4 KiB, BCCO has
43–56 clusters, exceeding its 52-page budget in five trials. Budget 64 covers
every cluster for every tested input, but BCCO still omits some types in seven
trials per view. Budget 128 covers all clusters and eligible types in all 140
new-policy trials. These are observed results, not a universal sufficient bound.

The extra selection bookkeeping is modest relative to preparation: at default
budgets, median selection/payload construction increased from 10.6 to 42.8 ms
for full Valkey, 11.4 to 24.0 ms for BCCO 2 MiB, and 14.3 to 55.0 ms for HNSW
perf-c2c. These measurements exclude clustering and cache-data preparation.

Provenance limits remain: the BCCO trace's exact paper-figure identity is not
confirmed; its 2-MiB view groups the same database rather than redoing native
conversion at 2 MiB. Packaged EFRB is illustrative, not the historical figure.
Full Valkey is the retained one-million-key diagnostic trace, not the
four-million-key performance run. Several other historical traces remain
unavailable. This is not coverage of every historical paper input.

## Where loading time goes

Measurements used the local Intel Core i7-14700KF host, WSL2 Docker, and pinned
artifact dependencies. Containers were limited to two CPUs, with 12 GiB for
Python and 6 GiB for Node. No application experiments ran on cluster machines.

The main backend cost is building cache histories, not reading SQLite. Under
cProfile, full Valkey spent 9.45 s in cache preparation versus 1.48 s loading
the database; BCCO spent 38.67 s versus 2.50 s. These are instrumented costs,
not normal end-to-end latency measurements. Cache preparation repeatedly
creates tiny index arrays and uses `np.add.at` for individual allocation/field
updates: about 1.05 million such updates for Valkey and 5.26 million for BCCO.

An offline prototype replaces these index arrays with a scalar update or a
small number of contiguous cache-set range updates, accounting for wraparound
and repeated sets. It preserves the existing data representation and all
allocation/field contributions.

| Input | Baseline cache preparation | Range-update prototype | Full returned output equal? |
|---|---:|---:|---|
| Full Valkey | 7.16 s | 3.81 s | Yes |
| BCCO, 2-MiB view | 23.00 s | 7.27 s | Yes |

These are one unprofiled invocation per implementation/input, in baseline-first
order, not a replicated speedup estimate. Equality covers the entire returned
cache structure. Additional small cases check positive/negative deltas,
wraparound, repeated cache sets, and zero-length updates. The prototype is
confined to the research script; the runtime implementation is unchanged.

There is another clear opportunity on repeated requests: the server constructs
a new Sampler, reads the database, and rebuilds cache data even when only the
representative-page selection changed. Reusing immutable trace/geometry-derived
results or separating the page-resampling response could avoid that work. Do
not simply cache the mutable Sampler: some methods change its data. Any cache
needs explicit invalidation and a bounded memory footprint. This opportunity
is source-derived; it has not been implemented or timed.

## UI computations that can be avoided

The huge-page row currently prepares 2,002 time buckets with 128 slots each
whenever type visibility changes. This happens for every mounted row, including
offscreen rows. At 226 pages that is 57,913,856 numeric cells, before JavaScript
array overhead. Only one time bucket is displayed. The cache heatmap similarly
re-aggregates all time buckets although it displays just the selected one.

Offline candidates compute only that bucket. Tests compared every bucket and
slot/set, with two visibility masks, against the actual helpers extracted from
the baseline UI. All values were equal for these fixtures. Numeric equality
also preserves the per-bucket inputs to the existing colour scale; it does not
replace a browser rendering test.

| Computation | Baseline median | Current-bucket candidate median |
|---|---:|---:|
| Huge-page slots, 19 BCCO rows | 22.94 ms | 0.130 ms |
| Huge-page slots, 226 BCCO rows | 237.79 ms | 1.434 ms |
| Cache visible-type totals, BCCO | 62.89 ms | 0.098 ms |
| Cache visible-type totals, Valkey | 71.23 ms | 0.109 ms |

Node 18.18.2; six warm observations after one warmup, alternating execution
order, same JavaScript realm. Each timing computes the selected bucket 500;
correctness checks cover all 2,002 buckets. The earlier cross-realm pilot is
excluded because it confounded global lookup costs. Medians here are derived
from the raw same-realm observations, averaging the middle two values.

These are computation times, **not measured browser responsiveness gains**.
The old path amortizes its precomputation over subsequent slider moves, whereas
the candidate does work for each selected bucket. Integration should test both
visibility changes and continuous scrubbing, potentially caching recently used
buckets. React updates, SVG rendering, layout, and paint remain additional costs.

Further source-derived candidates are mounting only visible page rows and
making the automatically generated text snapshot on-demand or asynchronous.
The prior large BCCO view had over 34,000 DOM elements. These changes need more
interface validation than the narrow arithmetic changes, especially scrolling,
selection, cross-highlighting, tooltips, and export behavior.

## Validation and next steps

- Selector regressions: twelve tests, including 300 randomized invariant cases,
  mandatory-page overflow, empty/zero budgets, requested type coverage, and
  actual Sampler payload/Flask JSON compatibility.
- Selector plus existing cache tests: seventeen passed.
- Full artifact regression discovery: 81 reported tests, successful, with one
  skipped allocator class because its SetBench submodule is uninitialized in
  this worktree. No changes touch that allocator or submodule.
- No frontend runtime code changed. The new selector's visual behavior has not
  yet been checked end-to-end in a browser; the prior browser timings concern
  the baseline selector's replay fixtures.

Next, integrate the narrow cache-update and current-bucket computations only
after reviewing these results, then repeat the interface checks with the
cluster-first payloads. Decide separately whether to raise the default budget
or provide explicit access to omitted clusters. No default-budget increase is
included in this branch so far.

## Evidence

Compact results and input/source hashes: [results-20260928.json](results-20260928.json).
Research drivers are listed in [README.md](README.md). Raw author-workspace
paths, relative to `C:/Users/trbot/Documents/ChatGPT/atc2026`:

- `artifact-tools/cluster-first-20260928/`: per-seed results and new payloads.
- `artifact-tools/camera-ready-profiles-20260928/`: cProfile output, complete
  cache comparisons, and `ui-computation-same-realm.json`/log.
- `artifact-tools/budget-latency-20260928/`: frozen earlier comparison inputs.
- `artifact-tools/rax-sampling-20260928/lifetime-audit.json`: rare-layout oracle.
- `PAGE_BUDGET_AND_LATENCY_RESULTS.md`: unchanged-selector budget/browser study.
- `PAPER_CLUSTER_BUDGET_AUDIT.md`: retained-trace provenance.

Large databases, rendered payloads, and raw application logs are not added to
this branch's tracked files.
