# Final-paper results and selection

This directory targets the October 16 camera-ready source, recorded in
`provenance.json`. It complements the frozen older campaigns; it does not pool
them or claim a fresh performance run of the integrated implementation.

## Regenerate saved results (seconds, no Docker)

From the repository root:

```bash
python3 artifact/final-paper/summarize.py
python3 artifact/final-paper/summarize.py --json > final-paper-summary.json
python3 artifact/final-paper/verify_selection.py
```

Output: Table 3's nine logging rows, the BCCO buffer comparison, Table 4's
four selection rows, and unrounded values in the JSON output. Expected BCCO
gain: **18.1%**, losses **52.0% → 43.3%**, mean peak RSS increase **1.3 GiB**.
Table 4: **12/12, 12/12, 11/12, 10/12** patterns found in all twenty trials,
with **99.0%, 99.3%, 91.5%, 91.3%** duration coverage, respectively.

`logging-cells.json` contains 190 individual observations: 120 from the general
ten-round campaign, 40 from the 20%-update ASCYLIB follow-up, and 30 from the
plain/fixed2/adaptive BCCO comparison. Each retains the native rate, worker-wait
intervals, available operation counts/RSS, source hash and audit status. HJ is
excluded because its native concurrent-update workload failed correctness checks.
The older search-only ASCYLIB and BCCO observations remain historical evidence.

Loss is `100 * (1 - mean(logging rate) / mean(plain rate))`; a small negative
loss is retained. Wait is computed per trial as summed phase-1 buffer-reuse
waiting divided by summed phase-1 worker elapsed time, then averaged across ten
trials. Final drain is excluded. Valkey recorded zero reuse waits throughout
the process; no missing worker denominator is invented. Native HashSkipList
throughput includes writer completion in its interval. Its separate reader-only
loss is **55.7%**, versus **60.2%** native loss; JSON also gives reader and writer
intervals and writer tails. Neither definition replaces the other.

The BCCO comparison uses baseline application code, local-NVMe logs, and the same
allocator in every arm. Fixed2 already reuses completed buffers. Adaptive adds
separate allocations on demand: two initial million-record buffers/thread,
four maximum, 40 bytes/record, with a 2-GiB aggregate cap on extra capacity.
The cap is accounting, not a preallocated pool. Mean peak RSS is the mean of
each trial's measured process peak; it is not reserved buffer capacity. Saved
commit/abort counters give mean abort-attempt fractions of **0.05%** plain and
**10.5%** adaptive, using `aborts / (commits + aborts)` per trial.

Successful follow-up raw traces were deliberately discarded after native
correctness, producer/write completion and exact-length checks. Full typed
scans ran at preflight, not on every timed trial. Small disposal/audit receipts
remain; this package does not advertise the discarded traces as downloads.

## Selection evidence and definitions

`selection-summary.json` preserves all **208** pattern/setting/budget/method
cells from the completed study: thirteen patterns, two initial page-sampling
settings, two page budgets and four algorithms. Each cell contains the mean
and success counts from twenty trials. The study comprised 440 shared-input
groups and 3520 algorithm/budget outputs. `selection-trials.json.gz` contains
all 440 individual trial receipts, including selected pages, per-pattern scores,
seeds and full-input duration denominators (1.3 MB compressed). The verifier
recomputes all 208 aggregate cells from those receipts, checks every expected
trial identity, and rejects missing/duplicate seeds or changed aggregates.
These are retained measurements, not new runs. Each exported receipt records
the SHA-256 of its original JSON; the export also checked every full-method
result against the separately retained paired baseline.

The eleven full database inputs remain outside this compact source package.
Together they occupy 62.3 GiB as SQLite files, before any archive compression;
a compressed archive size has not been measured. They are retained by the authors.
This release distributes the compact per-trial evidence and small runnable
examples, without requiring a bulk database download. The verifier checks saved
results; it does not rerun the full study. Exact full-study replay requires
those retained inputs and the frozen study environment.

Table 4 uses twelve patterns from the ten Table 1 baselines. The ablation prose
also includes a thirteenth rare optimized-InlineSkipList mixture. Keep those
scopes separate. Duration coverage first averages each pattern over twenty
seeds, including zeros; the geometric mean weights pattern/setting cells equally.
Relative gains are geometric means of paired complete/ablated mean-coverage
ratios. The protocol JSON records seeds, thresholds and exact scopes.

A success needs a qualifying page at a qualifying time; different trials may
use different pages/times. The evaluation grid has 2001 points on the full input
interval. The sixteen clustering fingerprint times are a different grid. Duration
coverage intersects displayed intervals with full-reference intervals on the
same page, then unions times across pages. Missing full-input targets are absent,
not failures. Valkey tests the traced 40-byte `robj` site, not untraced radix nodes.
HNSW tests vector starts, not continuation fragments or physical huge-page backing.
BCCO counts byte unions without double-counting enclosing buffers. Global
TPC-C/EFRB reclamation growth is not a page-local preservation predicate.

## Replay the integrated selector on a saved small input

After the Docker build in the main README:

```bash
bash artifact/run.sh select-pages artifact/data/efrb/allocs.sqlite \
  --out artifact/results/efrb-selection.json --seed 2026100900 \
  --page-size 4096 --buckets 2000 --page-budget 128 --record-budget 1000000
```

Output: JSON page histories, selection diagnostics and resolved configuration.
Allow 8 GiB RAM and minutes for the small bundled input. This is an entrypoint
check, not a replacement input for the full preservation study. Repeat with a
new output filename and `--mode no_per_time`, `--mode no_coverage_first` or
`--mode no_alternation` to exercise the three ablations. `--page-budget 32`
is explicit; it is not an automatic resource fallback. The GUI uses the same
algorithm and exposes the seed, page budget and record budget.

The accepted method combines history fingerprints and sixteen per-time
fingerprints, duplicate collapse, separate scaling/clustering, overlapping
cluster memberships, coverage first, and alternating random/distance choices.
Fingerprints use unreduced histories; budget costs count each complete page history after display reduction, without truncating selected pages. Mandatory perf
pages survive budget overflow and are reported explicitly. Initial whole-page
sampling `p/s` in the converter is separate from representative-page selection.
The exact executed selector and feature builder are frozen in the test fixtures;
tests compare the normal path with them across all four methods and seeded cases.

Full raw reconstruction is an expensive optional activity, not part of this
check: the recorded HSL stage reached about 202 GiB process-group RSS and took
46 minutes; TPC-C/EFRB feature preparation took 2.3 hours. Full study inputs are
not included in the compact release. Do not substitute later BCCO/ASCYLIB
captures for the fixed study inputs or treat a small example as an exact replay
of the full study.

## Other results

[Table 1](../README.md#3-reproduce-table-1-performance-comparisons) retains
matched allocator/workload and native timing definitions. TPC-C/EFRB's final
**21.1%** comes from the factor cohort; the earlier headline cohort gives 20.7%.
The [frozen camera-ready guide](../camera-ready-reproduction/README.md) preserves
backend/UI medians, factor studies and original measurement endpoints. Its
earlier sampling and stock-logger sections are historical; this directory
governs the final selection and logging claims. `cache` is cache preparation;
`complete` also includes the other backend preparation. Combined techniques can
be slower on an input; the BCCO result is retained, not corrected to a speedup.

The guide's saved-data verifier runs without recreating measurements. Current
backend/UI timings would be a separate cohort. No new artifact DOI is implied
by these source changes; the main README links the last published release.
