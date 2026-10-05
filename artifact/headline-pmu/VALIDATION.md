# Logging overhead and AIO validation

These are three separate, retained datasets. Publishing their measurements does
not require rerunning them. Each applies to its recorded logger and workload;
none should be relabeled as a complete performance test of every release change.

| Dataset | Cells | Scope |
| --- | ---: | --- |
| Original campaign | 400 | Ten application configurations, before/after variants, plain/logging, ten repetitions |
| AIO spot check | 18 | Baseline BCCO and HSL, three rotating plain/old/fixed blocks each |
| HSL timing follow-up | 18 | Baseline HSL, six balanced plain/old/fixed blocks, both rate definitions |

`plain` runs without allocation logging. `old` uses the prior logger; `fixed`
changes its AIO completion handling while retaining the same instrumentation,
probes, buffers, workload, allocator, compiler settings and placement. The old
and fixed logger binaries have SHA-256 hashes
`3deaa51a193ad797b040e2565ec9c665e0455535ca1da474ca8bf921601d4ba9` and
`96ebfbe4fed1d86923f774618a1197d0e796e4a7a15bf2edd521c9d1c98a50e6`.
Both follow-ups ran serially on Pyke, with measured traces/databases on NFS and
archive retention between trials. No completed cell was repeated or selected
by performance. The HSL follow-up rebuilt only benchmark timing reporting and
reused these exact logger binaries. Full-release sealing and HNSW query coverage
were outside this AIO-only comparison.

## AIO spot check

All 18 cells passed independent audit, with 72 PMU entries at 100% coverage,
zero reported wait errors, 12 trace archives and nine database archives checked.
The [cell data](aio-validation/numerical-summary.json) preserve operation counts,
record production, wait totals, all arm means/ranges and every block comparison.
The [audit receipt](aio-validation/audit.json) records archive verification;
its paths identify retained author evidence, not files bundled here.

| Application | Block | Plain ops/s | Old ops/s | Fixed ops/s | Fixed/old change |
| --- | ---: | ---: | ---: | ---: | ---: |
| BCCO | 1 | 967,488.674 | 497,076.336 | 484,564.787 | -2.52% |
| BCCO | 2 | 973,451.832 | 456,348.414 | 527,386.572 | +15.57% |
| BCCO | 3 | 972,997.456 | 471,715.104 | 474,019.526 | +0.49% |
| HSL | 1 | 4,661,983 | 1,953,103 | 7,237,990 | +270.59% |
| HSL | 2 | 11,658,391 | 2,447,275 | 6,889,223 | +181.51% |
| HSL | 3 | 12,167,632 | 5,360,712 | 4,020,082 | -25.01% |

BCCO counts committed transactions. HSL counts reader operations using the
native mixed-workload completion interval. Ratios of mean rates give fixed/old
changes of +4.27% for BCCO and +85.91% for HSL. The large HSL variability prevents
interpreting its favorable mean as an AIO speedup. BCCO logging throughput losses
relative to plain are 51.09% old and 49.00% fixed. These are descriptive results,
not proof of equivalence. Raw traces exceed terminal probe reports by 685 records
per BCCO logging cell and 13 per HSL logging cell; this is not exact equality or
proof of exhaustive semantic coverage. Summed worker waits overlap in time and
are not wall-clock stalls or an isolated overhead component.

## HSL timing follow-up

All six arm permutations were run once (blocks 4–9); each arm appears twice in
each position. The workload has 95 readers and one writer, 10M preloaded keys,
32/128-byte keys/values, a 256-MiB write buffer, and a nominal 10-second read
window, using CPUs 0–95 and memory interleaved across NUMA nodes 0 and 1.
Flushing and compaction remain enabled; WAL and synchronous writes are disabled.

The native rate divides reader operations by an interval that can extend through
writer completion and subsequent accounting delay. The additive reader-only rate
uses the earliest reader start and latest reader finish; it still reflects
interference from concurrent writer/background activity. The [complete report](hsl-timing/RESULTS.md)
and [cell data](hsl-timing/numerical-summary.json) retain every block and timing.

Across six blocks, fixed/old mean-rate change is +11.49% native and +1.74%
reader-only. Reader-only block changes range from -6.42% to +14.62%; there is no
consistent slowdown or gain. Both loggers still reduce reader-only throughput by
about 50% relative to plain (50.44% old, 49.57% fixed). The longest measured writer
tail is 7.722044 seconds; the largest separate post-worker gap is 2.163533 seconds.
Their specific causes are not established. These endpoint differences do not
retroactively reconstruct reader-only rates for the original campaign.

All 18 cells passed independent audit, including 72 PMU entries at 100% coverage,
12 trace archives, 18 database archives and 1,692 unchanged input/history hashes.
The [audit receipt](hsl-timing/audit.json) records that completed verification.
The [endpoint reports](hsl-timing/endpoint-reports.json) contain exact native and
worker report lines extracted from the byte-verified original logs, plus each
original log's hash. The analysis verifier checks endpoints and arithmetic; it
does not re-decompress the externally retained archives or reproduce timing.

`publication-manifest.json` records hashes of the retained evidence copies.
The original 400-cell numerical JSON and both validation numerical summaries
are copied unchanged. No historical result is replaced, and the portable full
400-cell measurement launcher remains separate unfinished work.
