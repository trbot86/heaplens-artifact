# Table 1 routing and two-worker EFRB figures

The main guide now calls `artifact/table1.py`, which selects the existing frozen
headline drivers with plain before/after measurements only. ASCYLIB uses dynamic
SSMEM, RocksDB enables RTTI, and counters use the recorded workload gates. Each
row runs ten alternating before/after pairs. The default historical 400-cell
plain/logging command remains available and unchanged in scope.

The entry point performs preflight, build and run sequentially under the existing
controller's locking, bounds and failure handling. It refuses existing output
paths and does not retry failed stages. The inherited build stage still prepares
paired binaries; this change does not claim faster builds. Only plain binaries
are measured through the Table 1 entry point. Final output adds plain before/after
throughput comparisons; individual PMU receipts remain available.

The old per-row performance commands are explicitly historical. They remain
available for the evaluator confirmations, allocator/layout factor comparisons
and the DVY four-layout helper. They issue a notice pointing to the current
Table 1 entry point. Their earlier results are not relabeled or removed.

EFRB diagnostic commands now accept an explicit worker count and default to two
workers. The README specifies `--threads 2` for Figures 4/5. Standalone EFRB's
Table 1 performance workload remains four workers; TPC-C/EFRB remains 24.

Five source files changed by earlier release fixes were still referenced directly
by the frozen campaign manifest. Their original, hash-verified bytes are now
bundled as overrides, preserving the historical source identity instead of
letting current artifact fixes break reconstruction.

Validation: 53 focused tests cover command routing, every documented Table 1
command, balanced schedules, native-rate aggregation, missing-cell rejection,
existing-output protection, failure stopping, historical retention and evaluator
workflows. All 8,870 regular frozen source files were checked against the manifest:
4,857 available in the release checkout and 4,013 submodule files from the verified
published source archive. This is source and orchestration validation, not a new
full native performance campaign or regenerated figure trace.

The Zenodo archive at version 2026.10.07.1 is unchanged. These additions are on
GitHub; publishing a new archival version is a separate action.
