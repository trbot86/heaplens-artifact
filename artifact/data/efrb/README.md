# Newly generated EFRB illustrative trace

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

## Separate full-profile prefill observation

`prefill-comparison.png` and `prefill-observation.json` describe a separate
October 6, 2026 local full-profile baseline trace, with corrected retirement
logging: 24 worker threads, 262,144 initial keys, range 524,288, five seconds of
search-only execution, single-thread prefill and no object segregation. They
do not describe or replace this directory's older `allocs.sqlite`.

At the default 2,000-bucket resolution, the full trace has 16 empty node sets,
32 approximately half-maximum sets and 16 maximum-count sets in buckets 1–30.
The second allocator chunk begins in bucket 31 and fills the empty sets.
The production backend agrees with independent live-address enumeration at
every bucket. The PNG uses observed counts and the production cache component's
color function and current theme; it is not an interactive GUI screenshot.

The JSON records the full trace's SHA-256 and selected counts. The 55-MB full
database is retained in the author evidence; it is not bundled here. Generate
a new one with the main README's Figure 5(a) command, then inspect early
prefill with node-only cache visibility. Neither exact timestamps nor column
alignment are expected to match across runs. This is qualitative trace
validation, not a performance measurement or a new check of panels (b)/(c).
