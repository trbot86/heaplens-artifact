# Final-paper integration candidate

Base: published main `89ec644`. Correctness/logger merge: `63e36fe`.
CR/backend/UI/final-selector merge: `e2e66b86`. Existing main release fixes are
retained; the earlier main checkout and development worktrees were not reset.

Completed checks before packaging:

- 199 correctness tests passed (18 opt-in skips).
- Native instrumentation: 11 header, one TPC-C custom-allocation, four C++
  new-expression and one custom-allocator tests passed from an immutable source
  archive with pinned dependencies.
- 259 combined backend/selection tests passed (19 opt-in skips), including the
  ordinary SQLite/backend/CLI route and exact executed-study equivalence.
- Frontend helper tests passed: continuations, 2,649 current-bucket oracle
  cases, 600 detail cases, million-record export/cancel/error and trace clocks.
- Full TypeScript checking reports 51 diagnostics, the same diagnostic multiset
  as the frozen CR frontend. This is a pre-existing limitation, not a clean
  typecheck. The changed pure helper modules pass their focused compilation.
- Converter regression: fourteen zero-extent/nested allocation cases passed.
- Portable saved analysis reproduces all nine final logging rows, the BCCO
  buffering ablation and all four final selection-table rows.

The final assembled package and saved-input replay checks are recorded below
when completed. Full application timing campaigns and large new figure captures
are not acceptance tests for this source integration. Historical native results
remain attributed to their original binaries. No visual browser/desktop control
was used. An author visual check of the integrated GUI is still useful.

Distribution limits: final selection summaries are packaged at the per-pattern
twenty-trial aggregate level; the full eleven input databases and individual
seed records are not part of this compact source candidate. Full frozen-study
replay packaging and large-input distribution remain explicit release tasks.
The README identifies diagnostic versus performance commands and historical
versus final figure numbering. The referenced October 9 DOI has not been
updated by this integration.
