# Final-paper integration validation

Accepted implementation: `a816b341`, on `codex/final-paper-integration`, based
on published main `89ec644` and CR `884fb19`. The November 2 checks below
supersede the earlier frontend typecheck and local-kernel limitations.

## Clean build and regression checks

- Built the actual artifact Dockerfile and dependency manifests from a fresh
  minimal context in 205 seconds. Image ID:
  `sha256:bc5b81e567754e0af2aa797fbc5a4022cc94525c6a9e1d9256d69d5ea67e4dab`.
- Extracted the committed source, including pinned SetBench/RocksDB dependencies,
  into that new image. The default **273-test suite executed 254 tests**, with
  19 explicit opt-in skips. Separate native runs now exercise **all 19 skipped
  tests successfully**. The initial 17-test follow-up covered 15 of those skips
  and repeated two ordinary header tests. The supplemental run covers final log
  writes, retirement ordering, ASCYLIB's read-only boundary, and Valkey worker
  flushing (plus two repeated Valkey source tests). No opt-in checks remain
  unexecuted. The first supplemental ASCYLIB attempt lacked its submodule in
  the test snapshot; adding the exact pinned `3c2d1a23` dependency resolved that
  setup error without changing the implementation. Its failed log is preserved.
- Full TypeScript checking and the Next.js production build pass with no errors.
  Eight React hook dependency warnings remain and need a focused state-update
  review; the successful GUI checks do not establish that every omitted
  dependency is harmless. Repairs include explicit React/D3
  types, null handling, UTF-8 lint configuration, stable list keys, and shared
  utilities moved out of Next.js page exports. Query parameters have a Suspense
  boundary. Lint and type checking remain enabled.
- All five frontend helper suites pass: continuation edges, 2,649 current-bucket
  comparisons, 600 detail comparisons, million-record export/cancellation/error
  cases, and per-trace clocks. Converter tests cover fourteen zero-extent and
  nested allocation cases.
- The saved-result summarizer reproduces the final logging and selection tables.
  Native and reader-only HSL throughput and writer endpoints remain separate.

The tested scientific dependencies are NumPy 1.25.2, pandas 2.1.1, SciPy 1.15.3
and scikit-learn 1.3.2. This is functional acceptance of the integrated source;
historical timing measurements remain attributed to their original binaries.

## Native backing check

The BCCO preflight passed on Pyke with Linux 6.8.0-137 under the shared experiment
lock. It verified independent jemalloc 5.3 instances and used PAGEMAP_SCAN to
confirm small-page backing followed by a 2-MiB huge page after process-local
MADV_COLLAPSE. The preflight exited and released the lock. No system-wide
settings or other processes were changed, and no full application was run.

## Saved inputs and GUI

Saved EFRB (16,404 objects) and Valkey (104,913 objects) replay checks establish
exact equality with frozen-study fingerprints, cluster memberships and pages
for all four methods, ordinary CLI equality, and old/new cache equality.
Input hashes remain unchanged; see `saved-replay.json`.

The production GUI was exercised through an isolated in-app browser:

- EFRB: 37 pages / 2,068 records / 7 represented clusters by default; resampling
  with seed 2026100900 and a 32-page budget produces 32 / 1,748 / 7.
- Valkey: 116 pages / 8,400 records / 58 represented clusters by default.
- Time changes, selected-page detail, per-type page/cache visibility and
  off-screen page rows render correctly. Unknown clocks are labelled in ticks.
- An oversized Valkey L2 request is rejected with the memory-budget explanation;
  the previous L1 view stays selected and usable, with no silent parameter changes.
- Snapshot export completed and its downloaded file contains eight snapshots,
  each covering all 37 selected EFRB pages. The button now uses the exporter's
  snapshot-count constant instead of the stale five-snapshot label.

The author handled the native save dialog. Temporary browser/service processes
were closed; no existing user tabs or unrelated services were modified.

## Scientific evidence and remaining release scope

All **440** retained selection trial receipts agree with their paired full-method
baseline receipts. All **3,520** method/budget outputs are present, and their
per-seed values reproduce all **208** aggregate cells. The 1.3-MB compressed
receipts and `artifact/final-paper/verify_selection.py` are included. No study
was rerun or pooled with a different cohort.

The eleven full study databases still exist remotely (62.3 GiB total); only
their presence and sizes were checked. No large database was scanned or
transferred. Public distribution of those inputs and full frozen-study replay
packaging remain release tasks.

Fresh full application performance campaigns and large figure captures were
not repeated for this integration. Figure command/configuration/phase tests
pass, including four-worker EFRB, HJ64 with pinned jemalloc, segregation-only
BCCO, and explicit 2,000-bucket conversion. Main and Zenodo remain unchanged
pending author review and publication authorization.
