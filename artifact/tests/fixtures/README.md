# Counter-parser fixtures

These small output excerpts exercise the ASCYLIB and TPC-C parsers in
`test_perfstat_results.py`. They come from two-thread packaging smoke runs
on September 22–23, 2026, not the paper's performance experiments.

The three ASCYLIB files retain the operation-total rows and throughput lines.
The two TPC-C files retain per-thread counts, aggregate index statistics, and
the global summary, so tests distinguish committed transactions from index
operations. Trailing whitespace was stripped; the selected values are unchanged.

The test module also supplies synthetic counter and benchmark records to
check arithmetic, missing counters, and durations other than one second.
