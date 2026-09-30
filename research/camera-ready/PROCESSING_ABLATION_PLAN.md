# Compact processing and interaction evaluation

## What this evidence should establish

Explain the obstacle before the mechanism: allocation histories can contain many
successive objects at the same address, and one object's lifetime can span most
of the displayed time range. Preparing every object/time/space combination, or
rebuilding every time bucket on each UI interaction, repeats substantial work.
The useful claim is that particular choices remove that work while preserving
specified answers or providing an explicit bound on retained detail.

Separate three questions: does the implementation compute the right result;
does a particular optimization reduce its cost; and is the resulting complete
tool usable at the demonstrated scale? The large-history browser stress answers
the third question only, unless paired with a controlled implementation change.
It does not establish a speedup by itself.

## Existing controlled evidence

See [the measured optimization report](OPTIMIZATION_RESULTS.md) for protocol and
raw-data pointers. These are local warm measurements with three trials per input
and implementation, not application throughput measurements on the paper hosts.

| Mechanism | Controlled comparison and result | Supported interpretation |
|---|---|---|
| Cache-range accumulation | Repeated-index arrays and `np.add.at` versus scalar/range updates, including complete cache-set cycles. Full prepared JSON hashes match. Valkey preparation: 11.90 to 8.70 s; BCCO: 27.20 to 12.04 s. Cache phases alone: 6.83 to 3.56 s and 22.24 to 7.09 s. | Avoiding per-object repeated-index construction materially reduces actual preparation cost. Database reading was not accelerated. |
| Computing UI summaries for the selected bucket | Old all-bucket and selected-bucket helpers match over 74,826,752 tested values; paired browser states match. BCCO 128-page cache-visibility response: 570.6 to 136.5 ms; page visibility: 446.0 to 226.8 ms. Slider response remains approximately 109 ms. | Computing every time bucket on visibility changes was unnecessary. This does not solve all-row rendering cost. The integrated frontend comparison changes both summary helpers and removes debug logging, so do not attribute the entire gain to one helper alone. |

These mechanisms use standard algorithmic ingredients. Explain their role in
making typed lifetime and page-layout inspection practical; do not claim prefix
sums, range updates, or on-demand computation as newly invented algorithms.

## Smallest useful additional processing ablation

### Priority 1: lifetime endpoints versus visiting every live bucket

Use one retained application trace containing long-lived allocations, at the
paper's fixed bucket count. Keep reconstructed lifetimes, page splitting, cache
geometry, type/field expansion, numeric representations, and output semantics
identical. Compare:

- Direct accumulation into every bucket in which each object contributes.
- A contribution at each lifetime endpoint followed by a cumulative sum.

For cache occupancy, use the same spatial range-update implementation in both
versions, so spatial and temporal improvements are not mixed. Keep null frees,
bucket-boundary behavior, same-bucket lifetimes, and signed updates identical.
Check full resulting arrays before timing. If exceptional timestamp order occurs
in a retained trace, either preserve its existing signed semantics in both
implementations or document exclusion; do not silently turn this into a
correctness change.

Measure this phase and complete preparation separately, with repeated interleaved
runs and peak process memory in fresh processes. A single realistic trace is
enough if the effect is material; a synthetic long-lived-object input can explain
scaling but cannot replace the application measurement. Bound slow baseline runs
and report timeouts as bounds rather than invented elapsed times.

This comparison is **planned, not yet measured**. The endpoint method appears
both in native type-size time series (`type_analysis/convert_to_db/sampler.cpp`)
and Python cache occupancy (`sifter_vis_d3/server/sampler.py`). Start with the
Python cache phase where an existing complete-preparation harness is available;
do not promise a second native ablation unless it adds explanatory value.

### Priority 2: reducing display histories within fixed time buckets

At fixed selected page IDs and bucket boundaries, compare full prepared histories
with the existing last-allocation-per-(address,type,bucket) representation. Report
record count, preparation/serialization time, payload bytes, browser load, and
memory. Keep fingerprints and cluster membership fixed: the current code builds
fingerprints from the full object dataframe and uses reduced histories for the
page payload, not for that fingerprint calculation.

This is a **detail-versus-cost comparison**, not an equal-output ablation. The
last-allocation representation can omit short-lived instances. State exactly
what is retained and relate it to the separate known-anomaly preservation study.
Do not infer anomaly preservation just from a lower record count. This comparison
is also **planned, not yet measured**.

### Separate UI ablation: selected-region detail construction

Implemented and measured September 29:
[selected-region detail results](DETAIL_OPTIMIZATION_RESULTS.md). Three paired
trials show a 28.9x/50.3x median selection-response improvement for one/16 dense
pages. Rendered-view comparisons and boundary/lifetime/field tests passed.

The large-history stress identified a narrower target than changing the sampler:
`ObjectLayout` maps the entire selected page's history to React components, and
`HoverableSplitBlock` checks liveness and visibility but not intersection with the
selected address range. Clipping hides off-screen objects without avoiding their
component/DOM construction. A fully packed 2-MiB page contains 65,536 32-byte
objects, even when only 64 KiB is selected for inspection.

The implemented comparison filters by interval intersection before creating detail
components and covers boundary crossings, nested containers, fields, address
reuse, and exact allocation/free endpoints. Visible screenshots and tooltips
match; the entire DOM deliberately differs because off-screen components
disappear. This establishes a UI engineering benefit, separate from the still
planned processing-engine comparisons above. Whole-page/viewport virtualization
remains outside this change.

## What not to disable or overclaim

- Keep containment/lifetime reconstruction and synthetic frees enabled. Removing
  them changes which objects exist; it is not a valid faster/slower equivalent.
  A small nested-region worked example and correctness tests establish their
  necessity. A reconstruction-specific scalability comparison would need its
  own correct reference implementation.
- Spatial splitting is currently a direct page-boundary walk. No distinct
  optimized splitting algorithm has been established to ablate.
- Sampling and representative-history budgets change what is shown. Measure
  coverage and responsiveness together, not as an equivalent-output speedup.
- Do not claim a historical hours-to-minutes improvement without its matched
  input, implementation, and measurements.
- Synthetic million-record UI fixtures retain fixed real cache/statistics panels
  and bypass the representative-record cap. They isolate frontend history cost;
  they are not complete million-record application/database loading experiments.

## Suggested paper footprint

Use one obstacle/mechanism paragraph with a short lifetime example, then a small
table or quantitative sentence reporting the strongest measured preparation
comparison. Add the prefix-sum result only after it is measured and if it helps
explain the design beyond the existing cache-range result. Keep UI stress and
coverage evidence separate. There is no need for a large new evaluation section
or a sweep of every configurable parameter.
