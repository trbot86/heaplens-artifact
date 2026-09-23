# Newly generated EFRB teaching trace

This is a **submission smoke-test trace**, not the historical paper input.
Generated on September 23, 2026 UTC (September 22 in Toronto), in the packaged
Ubuntu 22.04/Clang 14.0.6 container on x86-64 WSL2.

Command: `bash artifact/run.sh legacy ascylib_efrb --profile smoke`

Two threads, 4,096 initial keys, key range 8,192, one-second search-only run,
sample proportion 1.0, one page per type (`s=1`). Historical baseline ASCYLIB
source plus the documented Clang compatibility patch; no segregation or
parallel-prefill optimization selected.

Integrity check passed; SUPERTABLE has 16,414 records, FIELDS 125, STATS 7,
ALIGNMENT 11, LINES 21,014, and PERF 0. This demonstrates trace generation
and supports a small interactive walkthrough. It does not validate paper
overheads, quantitative speedups, or rare-pattern recall.
