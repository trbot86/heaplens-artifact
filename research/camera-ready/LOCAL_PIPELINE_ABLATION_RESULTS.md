# Local processing, loading, and interaction ablations

The subsequent [matched backend 2x2](BACKEND_MATRIX_RESULTS.md) measures spatial
and temporal factors together. Use that matrix for joint attribution; the
standalone measurements below remain preserved. The configurations and results
are included here without the separately distributed paper sources.

September 29, 2026. Completed on the local Windows workstation, on
`codex/camera-ready-sampling`. Evaluator-facing `main` is unchanged. These are
research measurements, not changes to benchmark defaults. Earlier drafts and
the earlier 68-KiB interaction measurements remain preserved separately.

## Summary

All times below are medians of three interleaved paired trials, after discarded
warmups. Each row compares the same input and a single implementation factor.
The stages are separate experiments; their speedups must not be multiplied.

| Stage and input | Without technique | With technique | Finding |
| --- | ---: | ---: | --- |
| Native Valkey conversion: temporal prefix sums | 2.074 s | 1.694 s | 18.3% less conversion time |
| Valkey cache preparation: temporal prefix sums | 13.642 s | 3.599 s | 3.79x faster |
| BCCO cache preparation: temporal prefix sums | 5.743 s | 7.138 s | Direct accumulation is faster here |
| Valkey database to usable UI: bucket-reduced histories | 9.914 s | 10.433 s | No loading improvement |
| BCCO database to usable UI: bucket-reduced histories | 12.508 s | 12.701 s | No material loading improvement |
| Select 64 KiB within one dense 2-MiB page: filter before component creation | 18.751 s | 0.381 s | 49.2x faster |

## Environment and controls

Local Intel Core i7-14700KF, Windows/WSL2 Docker, NVIDIA RTX 3080. Browser trials
use fresh headless Edge 154 processes with hardware compositing/rasterization,
1440x1000 viewport, and the default browser heap policy. Both sides use the
same GPU; this does not isolate the GPU's contribution. Backend workers use
the frozen `heaplens-atc26:submission` image, two CPU equivalents, a 12-GiB
memory limit, and one BLAS/OpenMP thread. Frontend serving uses the same frozen
candidate or baseline builds throughout. No other study ran concurrently.

Native conversion uses the full retained Valkey log (1,016,169 events), 4-KiB
pages, p=1, s=1, 3,000 time buckets, seed 20260929, and the field dump. Each trial
uses a disposable copy: the converter temporarily extends its input file.
Canonical inputs are mounted read-only, and restoration of each copy is checked.

Backend preparation uses the retained Valkey and TPC-C/BCCO databases, with
4-KiB and 2-MiB pages respectively, 2,000 time buckets, seed 20260929, and the
128-page/100,000-history-record GUI budgets. Hashes of frozen sources, image,
and inputs are retained. The native and GUI bucket counts differ deliberately;
these are separate stages, not an end-to-end pipeline timing of one configuration.

## 1. Native database construction

The research binary switches between endpoint updates followed by cumulative
sums and direct signed updates to every subsequent bucket. Both modes are in
one `g++ -O2` binary; reconstruction, synthetic frees, splitting, sampling, and
SQLite writing are unchanged. This is a mechanical reference implementation,
not a recovered historical release.

Total conversion falls from 2.074 s (range 2.060–2.126) to 1.694 s
(1.642–1.711). The measured sampling/statistics/SQL phase falls from 1.017 s to
0.656 s; it includes more than the time-series kernel and must be named in full.
Reconstruction is unchanged, approximately 0.72–0.74 s. Input copying and
post-run correctness hashing are outside conversion timing.

All six SQLite tables have identical schemas, row counts, and sorted logical
row hashes across all six measured trials and the warmup. Database size is
54,403,072 bytes in every trial. This supports an equal-output speedup claim.

## 2. Temporal cache preparation

The direct reference retains the production spatial range-update helper, but
applies each object's contribution to a NumPy slice spanning its lifetime.
The prefix version records allocation/free endpoint deltas, then cumulatively
sums over time. There is no artificially slow Python loop over time buckets in
the reference. Field expansion, geometry, reconstruction, and output code are
the same. Null, same-bucket, and reversed lifetime endpoints retain current
semantics. This isolates temporal accumulation, not spatial range updates.

| Input | Direct cache preparation | Prefix cache preparation | Direct full preparation | Prefix full preparation |
| --- | ---: | ---: | ---: | ---: |
| Valkey | 13.642 s | 3.599 s | 19.093 s | 9.040 s |
| BCCO | 5.743 s | 7.138 s | 9.553 s | 10.967 s |

Full preparation includes database reading, statistics, page preparation,
cache preparation, and JSON serialization; it excludes HTTP and browser work.
Complete prepared-payload hashes match across all seven runs per input.
An additional 503 oracle/whole-method cases passed.

An untimed diagnostic of base objects before field expansion helps explain
the contrast. In Valkey, 74.61% span at least 1,000 of 2,000 buckets; the median
span is 1,237. In BCCO, 95.15% begin and end in the same bucket, and the median
span is zero. The direct method skips these zero-width intervals. Thus prefix
sums avoid substantial lifetime-dependent work on Valkey, but are not a
universal speedup. These distributions support this explanation; they do not
isolate every source of runtime difference.

## 3. History reduction and actual database-to-UI loading

Freeze the selected 128 page IDs and clustering for each input, then toggle
only display-history reduction. The full-history variant does not reselect
pages to fit a record budget. Both versions retain identical cache output and
clustering, but their page histories intentionally differ. This is not an
equal-output optimization or an anomaly-recall measurement.

| Input | Selected histories, full / reduced | Prepared payload, full / reduced | Preparation, full / reduced | Database to usable UI, full / reduced |
| --- | ---: | ---: | ---: | ---: |
| Valkey | 8,488 / 7,514 | 70.384 / 70.223 MB | 8.438 / 8.875 s | 9.914 / 10.433 s |
| BCCO | 51,136 / 42,232 | 67.469 / 65.840 MB | 10.984 / 10.864 s | 12.508 / 12.701 s |

MB means decimal megabytes. The complete prepared object counts are 1,022,156
and 469,850 respectively; reducing histories does not avoid reconstructing
these objects or computing the cache data. Actual loading trials make a fresh
backend preparation request, transfer and parse its response, and render the
UI. They do not replay a cached prepared fixture. Correctness hashing is
disabled in the timed HTTP path, having been performed separately.

End-to-end ranges are Valkey full 9.731–10.344 s, reduced 9.996–10.580 s;
BCCO full 12.098–12.994 s, reduced 12.432–12.979 s. No substantial loading gain
is established. These traces therefore do not substantiate an hours-to-minutes
claim about bucketing, nor a claim that history reduction is useless on more
heavily reused address ranges. A historical configuration or a separately
motivated reuse-heavy input would be needed to examine that earlier bottleneck.

## 4. Exact 64-KiB detail selection

A page budget alone does not bound rendering work: one 2-MiB page can contain
65,536 distinct 32-byte objects. Previously, the detail view created components
for the entire page before determining which belonged to the selected region.
The optimized version filters histories before component creation, retaining
overlapping/enclosing objects, relevant lifetime events, and expanded fields.
It does not sample away objects in the selected region or virtualize scrolling.

| Prepared fixture | Selection before / after | Speedup | Object rectangles before / after |
| --- | ---: | ---: | ---: |
| One dense page, 65,536 records | 18.751 / 0.381 s | 49.2x | 65,536 / 2,048 |
| Sixteen dense pages, 1,048,576 records | 21.395 / 0.412 s | 51.9x | 65,536 / 2,048 |
| 128 pages, 1,000,000 records | 3.077 / 1.162 s | 2.65x | 7,813 / 2,048 |

The single-page input fits the default record budget. The million-record
fixtures deliberately exceed it to test scaling, not the default selector.
All 18 measured browser trials verified a 65,536-byte selection and expected
rectangle counts (raw SVG counts include two extra clipping rectangles).
Response time runs from handler entry to the second animation-frame callback;
it is a responsiveness proxy, not a physical display/presentation timestamp.

Initial fixture loading is effectively unchanged: approximately 0.98 s,
1.65 s, and 1.91–1.92 s respectively. Sampled heap usage drops substantially
for the dense fixtures but not for the 128-page fixture; without forced GC,
these samples should not support a universal memory-reduction claim.

These are fresh paired measurements at exactly 64 KiB. The previous drag
selected 68 KiB, and its results remain in
[DETAIL_OPTIMIZATION_RESULTS.md](DETAIL_OPTIMIZATION_RESULTS.md). The huge-page
overview has 128 16-KiB slots; brushing snaps to 4-KiB boundaries. The new harness
checks actual snapped width instead of inferring it from the whole SVG width.

The unchanged renderer has prior pixel-equivalence checks in the earlier
report. This batch checks dimensions, counts, errors, and cleanup, not new
pixel-equivalence pairs at 64 KiB. Post-campaign regression tests passed:
600 randomized detail-helper cases plus boundary/lifetime/nesting/field tests,
2,649 current-bucket cases, and 26 Python selection/cache-limit tests.

## Suggested compact paper wording

"Temporal aggregation must account for objects that remain live across many
time buckets. HeapLENS records allocation and deallocation deltas and computes
prefix sums, avoiding repeated updates throughout each lifetime. On the Valkey
trace, this reduces cache preparation from 13.64 s to 3.60 s with identical
output. The benefit depends on lifetimes: on BCCO, where 95% of reconstructed
objects begin and end in the same bucket, direct accumulation is faster
(5.74 s versus 7.14 s)."

"Limiting the number of pages does not by itself bound interface cost. A
single 2-MiB page can contain 65,536 32-byte objects. Filtering histories to the
selected address region before constructing display components reduces the
response time for selecting 64 KiB of this page from 18.75 s to 0.38 s, while
retaining all 2,048 objects in the selected region."

Accompany these sentences with the environment and three-pair protocol. The
advance to explain is the problem-specific handling of scale and preserved
semantics; prefix sums and early filtering are established techniques.

## Evidence, limits, and cleanup

Compact results: [processing JSON](processing-ablation-results-20260929.json)
and [detail-selection JSON](detail64-ablation-results-20260929.json).
Author-local evidence is in `artifact-tools/processing-ablation-20260929/`,
`artifact-tools/detail64-ablation-20260929/`, and
`artifact-tools/history-load-ablation-20260929/` in the parent workspace.
The processing bundle contains source snapshots, manifests, per-trial logs,
hash checks, and ranges; it excludes database and prepared-payload copies.

Every measured trial completed. Worker, cache, browser-interaction, browser
trial, and campaign time bounds were enforced; no timeout or OOM was observed.
All study browser processes were cleaned up, and the local history server and
UI servers are stopped. No remote experiments, commits, or pushes were made.
Tests initially lacked TypeScript when invoked directly on Windows and were
rerun successfully in the artifact image with its installed dependencies.

This is a bounded first-pass ablation, not a complete rollback of every
processing technique. Reconstruction, interval splitting, synthetic frees,
and spatial range updates were held fixed. Their necessity/correctness should
not be presented as a separately measured speedup from this campaign.
