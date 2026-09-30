# Processing and interface optimizations: paper material

Author working material. Keep the backend matrix separate from the interaction
table: their times measure different operations. The prose below is written as
a self-contained account, without submission-history language. The tables use
seconds throughout; round to two decimals in the paper.

## Mechanism descriptions

### Preparing cache-set occupancy

An object's layout can contribute to many cache sets and remain live across
many time buckets. Directly updating every intersected cache line in every
bucket repeats work in both dimensions. HeapLENS reduces this work in two ways.
First, consecutive cache lines visit cache sets cyclically. Rather than
enumerating the set of every line, HeapLENS adds the number of complete cycles
to all sets and updates the remaining contiguous ranges. For example, an object
spanning 130 cache lines in a cache with 64 sets contributes twice to every set
and once more to two consecutive sets. The same calculation applies to the
typed fields included in the display. Second, HeapLENS records these
contributions at allocation and deallocation time buckets and computes prefix
sums along the time axis, rather than updating every bucket throughout the
object's lifetime. Both transformations preserve the bucketed occupancy values.

### Preparing the displayed time slice

When the user changes which object types are visible, HeapLENS must update the
page-slot occupancies and cache-set totals shown in the interface. Previously,
it recomputed these values for every time bucket in the recorded execution,
although only one bucket was displayed. HeapLENS now computes them only for the
selected bucket and computes the newly selected bucket's values when the user
moves the time slider. For a view containing 128 huge pages, each divided into
128 slots, this reduces the slot-summary array from 32,800,768 values across
2,002 bucket entries to 16,384 values for the selected entry.

### Constructing selected-region details

A page-count limit does not bound the cost of displaying individual objects:
one 2-MiB page can contain 65,536 32-byte objects. Constructing display components
for the entire page and clipping them to a selected region still incurs the
cost of constructing the hidden components. HeapLENS first filters object
histories to those intersecting the selected address region, retaining objects
that enclose the region and the events and fields needed to display their
lifetimes. Only these histories are passed to component construction. This
reduces display work without sampling away objects within the selected region.

## Backend evaluation text and table

| Spatial range updates | Temporal prefix sums | Valkey cache / preparation (s) | BCCO cache / preparation (s) |
| --- | --- | ---: | ---: |
| No | No | 100.77 / 105.99 | 6.51 / 10.25 |
| Yes | No | 13.35 / 18.63 | 5.58 / 9.37 |
| No | Yes | 5.85 / 11.06 | 19.97 / 23.72 |
| Yes | Yes | 3.61 / 8.90 | 7.01 / 10.81 |

Suggested caption: "Cache preparation / complete backend preparation in seconds;
medians of three interleaved trials per variant. Complete preparation includes
database reading, statistics, page preparation, cache preparation, and JSON
serialization; it excludes network transfer and browser rendering. All four
variants produce identical prepared output for each input."

The [LaTeX table](backend-matrix-table.tex) and
[full results with ranges](BACKEND_MATRIX_RESULTS.md) are generated from the
per-trial records. The slowest Valkey reference varies from 85.13 to 103.07 s
in its cache phase; the median is not a claim of negligible variability.

Suggested methods text:

"We evaluate spatial range updates and temporal prefix sums in a 2x2
experiment on retained Valkey and TPC-C/BCCO traces. All variants use the same
inputs, clustering seed, 2,000 time buckets, cache geometry (32 KiB, eight-way,
64-byte lines), and 128-page/100,000-history-record selection budgets. The
spatial reference enumerates cache-line indices using NumPy accumulation;
the temporal reference updates a NumPy slice spanning each lifetime. The
implementations share reconstruction, field expansion, page selection, and
serialization. We verify equality of the complete prepared output. Measurements
use an Intel Core i7-14700KF workstation, with fresh Linux containers limited to
two CPU equivalents and 12 GiB and one BLAS/OpenMP thread. We report medians of
three interleaved trials per variant after discarded warmups."

Suggested results text:

"On Valkey, spatial range updates and temporal prefix sums reduce cache
preparation from 100.77 s to 3.61 s and complete preparation from 105.99 s to
8.90 s. Their benefits overlap: spatial updates reduce cache preparation by
7.55x without prefix sums, but by 1.62x with prefix sums. BCCO behaves
differently: range updates alone are fastest at 5.58 s, compared with 6.51 s
for direct accumulation without either technique and 7.01 s with both."

"The value of temporal aggregation depends on object lifetimes. In the Valkey
trace, 74.6% of reconstructed base objects span at least half the timeline. In
BCCO, 95.1% begin and end within the same bucket, so direct accumulation often
has no interval to update. The endpoint implementation still adds and subtracts
their contributions in that bucket, where they cancel. Thus the temporal optimization need not improve every
trace, even though it removes work proportional to long lifetimes."

These lifetime percentages are before field expansion. They explain a mechanism
and input difference, not a separately controlled causal attribution.

## Interface evaluation table

| Operation and input | Eager construction (s) | Restricted computation (s) |
| --- | ---: | ---: |
| Initial browser view, BCCO, 128 huge pages | 2.140 | 1.509 |
| Toggle visible cache types, same view | 0.571 | 0.137 |
| Toggle visible page types, same view | 0.446 | 0.227 |
| Select 64 KiB, one dense huge page | 18.751 | 0.381 |
| Select 64 KiB, sixteen dense huge pages | 21.395 | 0.412 |
| Select 64 KiB, 128-page million-record view | 3.077 | 1.162 |

Suggested caption:

"Frontend responsiveness with identical input payloads. The first three rows
compare eager all-bucket summaries with selected-bucket summaries; the second
implementation also removes debug logging in the replaced aggregation. The last
three compare constructing all page details with filtering to the selected
address region before component construction. Each row reports medians from
three interleaved trials per implementation. Initial readiness and interaction
latency end at a second animation-frame callback; they are not compositor
presentation measurements."

Suggested text:

"The frontend experiments use Edge 154 with hardware acceleration on an
NVIDIA RTX 3080. The selected-bucket experiment uses a 1280x720 viewport and
identical prepared payloads; it excludes backend preparation. The detail
experiment uses a 1440x1000 viewport and verifies an exact 64-KiB selection in
each trial. On a single dense huge page, filtering reduces the constructed
object rectangles from 65,536 to 2,048 and the selection response from 18.75 s
to 0.38 s. This input fits the default record budget; the million-record views
deliberately exceed it to test scaling. Computing selected-bucket summaries
improves visibility changes, but does not materially improve slider dragging
in the 128-page BCCO view (approximately 109 ms)."

For a smaller table, retain the BCCO cache toggle and the single-dense-page
selection; they demonstrate distinct mechanisms without all stress configurations.
Do not describe the frontend bundle as individually isolating each summary helper.

## Optional supporting results

Native prefix sums reduce full Valkey log-to-database conversion from 2.074 s
to 1.694 s at 3,000 buckets. This uses 1,016,169 input events and preserves all
six SQLite tables' schemas, row counts, and sorted logical contents. The native
reference accumulates each signed event over subsequent buckets; reconstruction,
sampling, and database writing are otherwise unchanged. This is a separate
measurement, not a component that can be added to the matrix's medians.

| Display histories | Valkey full / reduced | BCCO full / reduced |
| --- | ---: | ---: |
| Records in the fixed selected pages | 8,488 / 7,514 | 51,136 / 42,232 |
| Actual database-to-UI readiness (s) | 9.914 / 10.433 | 12.508 / 12.701 |

History reduction changes retained temporal detail, unlike the equal-output
optimizations above. It does not materially accelerate loading on these two
traces. Include this distinction if making a performance claim about reducing
histories; do not use these data to assert a large bucketing speedup.

## Evidence pointers

- [Backend matrix](BACKEND_MATRIX_RESULTS.md): ranges, output checks, and interpretation.
- [Local pipeline report](LOCAL_PIPELINE_ABLATION_RESULTS.md): native, history,
  temporal-only, and exact-region experiments.
- [Integrated optimization report](OPTIMIZATION_RESULTS.md): selected-bucket
  experiments, correctness checks, and earlier spatial-only measurements.
- [Earlier detail report](DETAIL_OPTIMIZATION_RESULTS.md): mechanism and prior
  visual-equivalence checks; its 68-KiB timing rows are not used in this table.

All of these mechanisms use established algorithmic ingredients. Their role
here is to make typed lifetime/layout inspection practical at the measured
scale, not to claim invention of prefix sums or demand-driven computation.
