# Processing, loading, and interaction ablations

Update: the bounded local first pass is now complete. See
[LOCAL_PIPELINE_ABLATION_RESULTS.md](LOCAL_PIPELINE_ABLATION_RESULTS.md) for
the measured scope, results, and updated paper wording. The original plan below
is preserved; its prospective status and older selection timings are historical.

September 29, 2026. Author working plan for `codex/camera-ready-sampling`.
This extends [the earlier compact plan](PROCESSING_ABLATION_PLAN.md), which is
preserved. The additional experiments below have **not been run**. Existing
measurements are identified explicitly. No evaluator-facing defaults change.

## Paper text: selected-region detail rendering

### Mechanism paragraph

Selecting representative pages does not by itself bound rendering cost: a
2-MiB page can contain 65,536 32-byte objects. Clipping the drawing to a small
address range hides irrelevant objects but does not avoid constructing their
graphical components. HeapLENS therefore filters the page's history before
constructing the detail view, using the selected time, visible types, and
intersection with the selected address range. Intersection tests retain objects
that cross or enclose the range, including enclosing objects needed to display
expanded fields. For example, inspecting 64 KiB of such a densely packed page
requires components for 2,048 objects rather than all 65,536. The page's prepared
history remains available for inspecting other times and regions; this
optimization does not further sample the recorded objects.

### Separate, measured evaluation sentence

In a controlled browser test containing sixteen densely packed 2-MiB pages
(1,048,576 live 32-byte objects), filtering before detail construction reduced
median response time for selecting a 68-KiB region from 21.91 s to 0.436 s
(50.3x), across three paired trials.

The accompanying experimental-method text must identify this as a synthetic
frontend stress test, with prepared inputs and database preparation excluded.
The timing is pointer release to the second animation-frame callback, not a
direct compositor-present measurement. The illustrative 64-KiB example above
is a derived count; the measured gesture selects 68 KiB and retains 2,176
objects. See [the complete report](DETAIL_OPTIMIZATION_RESULTS.md) for the
environment, variability, other inputs, and rendered-equivalence checks.

### Scope notes for authors

- The helper still scans the selected page's history. It sorts and constructs
  components only for retained events; it is not an interval index or viewport
  virtualization. Selecting an entire dense page can still be expensive.
- The field fallback also preserves cases where a field intersects the range
  although the stored parent fragment does not. Boundary, lifetime, reuse,
  zero-size-marker, field, and nonmutation tests cover the implementation.
- Standard interval filtering is not a new algorithm. The supported point is
  that page-level sampling alone does not bound UI work, and applying the
  display restrictions before component construction removes a measured cost.

## Stage boundaries and factors

Use controlled implementations within one frozen source tree, rather than
checking out a substantially older system with different correctness behavior.
A reference with an optimization disabled is not necessarily a recovered
historical implementation. Label it accordingly.

| Stage | Factor and controlled reference | Measurements and invariants |
|---|---|---|
| A. Raw logs to SQLite database | Native type-size time series: endpoint updates plus a prefix sum versus applying each signed event's change to every subsequent bucket. | Conversion wall time, time-series phase, peak RSS, database bytes and rows. Same reconstructed events, selected pages, bucket boundaries, integer representation, and logical database contents. |
| B. Saved database to usable UI | Python cache temporal accumulation: lifetime endpoints plus prefix sum versus direct bucket accumulation, with spatial accumulation held fixed. | Cache-phase time and complete server preparation, then an actual database-open-to-ready measurement. Equal cache arrays and prepared payloads. |
| B. Saved database to usable UI | Spatial cache accumulation: range/cycle updates versus repeated-index accumulation, with temporal accumulation held fixed. | Same metrics and equal outputs. An existing paired server-preparation comparison is available. |
| B. Saved database to usable UI | Page display histories: full histories versus last allocation per `(address, type, time bucket)`. | Prepared record counts, preparation/encoding time, payload bytes, browser loading and memory. Same page IDs, fingerprints, and clusters. This changes retained detail; assess known-pattern preservation separately. |
| C. Visibility changes | Summaries for every time bucket versus the selected bucket only. Separate page-slot summaries from cache visible-type totals where attributing individual gains. | Input-to-frame response and temporary allocations, with identical input payload and visible state. Existing integrated measurements combine both helpers and debug-log removal. |
| C. Selecting a detail region | Construct components for the page history versus filter before sorting/component construction. | Input-to-frame response, component/DOM counts, sampled JS heap, and equal visible results. This paired comparison is already measured. |

Keep initial UI rendering and subsequent interactions distinct even when they
share a helper. Selecting a region, changing time, toggling types, expanding
fields, and scrolling are different operations; attribute gains to the measured
operation rather than reporting a generic "UI speedup."

For stage B, record the subphases of one complete load: SQLite reading, object
preparation, fingerprinting/clustering/selection, cache preparation, encoding,
HTTP transfer, browser decoding, and initial rendering. Some implementation
phases share work; do not force overlapping timings into an additive accounting.
Measure the actual complete interval as well. Prepared-payload replay isolates
browser work but is not a database-loading experiment. Do not add independent
phase medians and call the sum a measured end-to-end time.

## What "without buckets" means

Three distinct uses of time buckets must not become one ablation factor:

1. **Time-series resolution.** Native conversion writes bucketed per-type size
   series to `LINES`; the server constructs bucketed cache arrays. Changing this
   resolution changes the represented times. A fully detailed reference would
   use event/change-point times, not allocate a bucket for every nanosecond.
   Designing that reference is separate work, not a prerequisite for testing
   prefix sums at the paper's fixed resolution.
2. **Display-history reduction.** The server retains the last allocation in
   each `(address, type, bucket)` group for page display. Disabling this reduction
   restores histories at the same addresses within a bucket; it does not require
   removing time buckets from cache or size-series computations. This is the
   priority comparison for quantifying the cost of retaining full histories.
3. **Eager UI computation.** Computing summaries for all buckets versus only
   the selected bucket changes when work is performed, not temporal resolution.

Display-history reduction currently happens after opening the saved database.
Fingerprints use the full object dataframe; the reduced histories become the
page payload. Cache preparation also uses the full data. Thus this reduction
must not be credited with shrinking the native allocation table or accelerating
native database construction. Measure its downstream effects instead.

Freeze the selected page IDs before the full/reduced-history comparison. Do not
let the record budget silently select fewer pages for the full-history variant:
that would mix history reduction with page coverage. The external experiment
memory limit still applies. Report detail/known-pattern differences alongside
costs, rather than describing this comparison as equal-output acceleration.

## Correct references for prefix sums

For a simple lifetime example, an object contributing from bucket 10 up to (but
not including) bucket 1,990 affects 1,980 buckets. Direct accumulation visits
those buckets for that object; endpoint accumulation records a positive change
at 10 and its negative at 1,990, then shares a cumulative pass across objects.
This example is explanatory; actual tests must preserve the implementation's
exact allocation/free boundary conventions and sentinel buckets.

Native code receives signed allocation/free events. A particularly simple exact
reference adds each event's signed size to the suffix beginning at its bucket,
instead of updating that endpoint and later taking a cumulative sum. This keeps
reconstruction and pairing unchanged. Use compiled loops, not an intentionally
slow interpreter reference. It measures the chosen accumulation technique, not
the best possible alternative algorithm.

For Python cache arrays, use vectorized direct range/suffix accumulation with
the same spatial helper. Preserve type/field expansion, full cache-set cycle
multiplicities, null frees, reversed/same-bucket endpoints, numeric types, and
sentinels. A signed-suffix reference can preserve even exceptional timestamp
ordering without changing lifetime semantics. Avoid Python element-by-element
loops that would confound the comparison with interpreter overhead.

Verify full arrays on small and representative inputs before reporting speedup.
For native output, compare schemas and canonically ordered logical rows, not
the raw SQLite file hash. For equal-output server factors, compare canonical
payloads as well as the affected arrays. Keep correctness work outside the
timed region but require it for each reported configuration.

## Bounded execution protocol

These are proposed first-pass limits, to be enforced by the harness before
running the slow references:

| Work | Initial wall-clock ceiling per attempt |
|---|---:|
| Isolated accumulation or individual interaction | 30 s |
| Complete saved-database initialization | 120 s |
| Complete native conversion | 300 s |

1. **Manifest first.** Record input hashes, event/history/page/type counts,
   bucket counts and boundaries, cache geometry, source hashes, compiler/runtime,
   machine/resources, browser viewport, and warm/cold policy. Current defaults
   differ: native conversion uses 3,000 buckets, the GUI/server uses 2,000.
   Recover the actual paper configuration and pass each explicitly; do not
   infer one stage's setting from the other.
2. **Run the optimized path first.** Establish its costs and estimate the direct
   reference's bucket visits and dense-array sizes. Reject clearly excessive
   sizes before allocation. Start with small equality fixtures and progressively
   larger, complete histories, not the largest trace with every optimization off.
3. **Preserve semantic units.** Kernel pilots can use already reconstructed
   complete lifetimes. Native pilots need valid logs with the required enclosing
   regions and their events; do not arbitrarily cut logs and break lifetimes.
   Subset/microbenchmark results must not be labeled whole-application timings.
4. **Isolate writable inputs.** The native converter opens the input log for
   writing, temporarily doubles its length, and normally restores it in its
   destructor. It also recreates database tables in `allocs.sqlite` in its working
   directory. Each attempt therefore needs a disposable physical or copy-on-write
   input copy (never a hardlink) and a private working directory. Verify the
   canonical input remains unchanged. Copying is outside conversion timing and
   recorded separately. A killed attempt must not supply the next attempt's log.
5. **Bound resources and stop the whole attempt.** Use an external watchdog and
   a dedicated process group/container, so a stalled browser event loop cannot
   defeat the deadline. Use explicit memory limits no larger than the previous
   12-GiB backend and 8-GiB UI-container limits; bound/monitor the separate browser
   process as well and retain its default JS heap policy. Check host headroom,
   estimate temporary input/output sizes, and enforce a private output quota or
   monitored disk ceiling. Confirm process-tree cleanup after every attempt.
6. **Escalate only after a successful pilot.** Stop increasing a reference's
   input size after its first timeout/resource failure. Do not repeatedly spend
   the same timeout to obtain three missing observations. Keep the first pilot
   campaign within 45 minutes; a larger campaign requires an explicit revised
   budget, not an automatic retry loop.
7. **Repeat tractable comparisons.** Use three interleaved fresh-process pairs
   initially, with identical resource limits and balanced order. Report medians
   and the individual trial range; add repetitions only where variability affects
   the conclusion. State whether OS file caches are warm. Do not drop host caches
   on a shared machine merely to obtain a cold label.
8. **Record censoring honestly.** Distinguish time limit, memory limit, disk limit,
   program error, and correctness failure. Report `>120 s (time limit)` when
   applicable, not a measured 120-s completion. Do not extrapolate a days-long
   runtime from a small pilot. A speedup lower bound requires the same input and
   timed scope, a completed optimized result, and a genuinely time-censored
   reference; an OOM is not such a bound. Keep partial files isolated and never
   publish them as completed databases or validated results.

## Execution order and paper footprint

1. Add the Python temporal-prefix reference to the existing preparation harness;
   validate at fixed resolution and run bounded pilots on a retained trace with
   long-lived objects. Report cache-phase and complete preparation costs.
2. Compare full versus reduced page histories on the same selected pages, then
   measure an actual database-open-to-ready interval. Start below the large
   synthetic million-history inputs; those already isolate UI costs.
3. Add the native prefix reference and phase timers on disposable logs. Report
   complete construction time even if the time-series phase improves greatly:
   reconstruction or SQLite writing may dominate.
4. Reuse the completed detail-rendering experiment. If individual UI-summary
   attribution is needed, isolate each helper instead of reusing the combined
   summary-plus-logging comparison as a single-factor result.
5. Only if tractable and useful, add a combined reference within a stage (for
   example temporal and spatial cache optimizations both disabled). Individual
   ablations are primary; their speedups cannot be multiplied to manufacture a
   total. No full cross-product across database, loading, and interaction factors
   is necessary. Leave event-resolution time-series representation for a separate
   study unless it fills an actual explanatory gap.

Keep containment reconstruction, synthetic frees, and correct page splitting in
every equivalent-output variant. Removing them changes the answer. There is no
identified separate optimized-versus-naive page-splitting implementation to test.
Likewise, moving export from startup to a user request defers work; report that
policy explicitly rather than treating an omitted export as faster completion
of the same work.

The intended paper result is a compact stage-labeled table: factor, input scale,
affected phase/operation, and before/after cost, with a clear marker for the
history-reduction comparison that changes retained detail. Include only measured
rows that explain a material obstacle. Keep raw results, correctness evidence,
limits, and implementation recipes with the research scripts. Do not expand this
into a parameter sweep or a claim that every standard ingredient is novel.

## Source map and existing evidence

- Native construction: `type_analysis/convert_to_db/{main,io_handler,sampler}.cpp`.
  `IOHandler` owns input expansion/restoration and SQLite creation;
  `sample_pages_and_record_stats` accumulates and cumulatively sums `LINES`.
- Server preparation: `sifter_vis_d3/server/sampler.py`, especially
  `get_last_object_per_bucket`, `get_clusters_of_pages`, and `get_cache_data`.
  `server.py`'s `init_app` connects preparation to the HTTP response.
- UI: `sifter_vis_d3/sifter/src/app/ui/{currentBucket,detailEvents}.ts` and their
  callers. The detail helper's integration is in `pagesComponent.tsx`.
- [Existing range and selected-bucket measurements](OPTIMIZATION_RESULTS.md).
- [Completed selected-region detail ablation](DETAIL_OPTIMIZATION_RESULTS.md).
- `benchmark_integrated_backend.py` supplies interleaved server phase timing and
  payload-equivalence checks; `profile_preparation.py` is diagnostic profiling,
  not the source of final unprofiled timing claims.

The limits and additional references in this document are a plan, not a claim
that the current harnesses already implement them. This planning change launches
no experiments and changes no production code or evaluator defaults.
