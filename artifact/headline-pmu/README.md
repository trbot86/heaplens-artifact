# Retained 400-cell PMU and logging results

This optional package reproduces the **analysis of retained measurements**, not
a new benchmark run. Run `python3 artifact/headline-pmu/summarize.py` from the
repository root. It checks the complete identity matrix and recomputes all 20
throughput-loss comparisons from the 400 per-cell rows. It needs only Python's
standard library, less than 10 MiB of input, and no PMU privileges.

The ten comparisons each have before/after variants, plain+PMU and
HeapLENS+reuse-wait+PMU arms, and ten repetitions. Logging-arm loss is
`100 * (1 - mean(logging throughput) / mean(plain throughput))`.
Negative losses are retained observations, not established logging benefits.
The wait probe, instrumentation, and storage costs are not isolated. Summed
worker wait time is not elapsed time and cannot simply be subtracted from it.
See [source-path scope](SEMANTIC_REVIEW.md) for coverage and denominator limits.

## Logger versions and validity boundary

Measurements used frozen source `7f4f5f20125ad0a2571abc8ddb0e98e13c7ae109`
with recorded author measurement overlays. They are not measurements of every
subsequent artifact revision. HNSW and Valkey preparation included the corrected
AIO completion handling. ASCYLIB, TPC-C and RocksDB preparation used the older
single-wait path with the wait probe. Accepted waits reported no errors, but
that does not measure the cost of the corrected implementation.

The artifact now waits for completion before buffer reuse and checks completion
status and returned byte count. These are per-request metadata checks, not
payload scans or checksums during timing. Targeted old/new-logger performance
validation is pending; do not relabel these historical numbers as overhead of
the current logger. Invalid interrupted/instrumentation attempts were preserved
as diagnostics; the two explicitly approved replacements fill their intended
cells without selection by performance.

## Full measurement reproduction: expensive, separate opt-in

**Budget 48 hours or more**, depending on machine and storage. This is not part
of the default smoke run. The original serial controller was host-specific;
this directory does not yet provide a portable full-campaign launcher. Do not
execute old recovery controllers or substitute the C++ HNSW trace diagnostic
for the headline Python-binding workload.

Storage observed for the completed campaign:

| Retained successful data | Source bytes | Compressed bytes |
| --- | ---: | ---: |
| 140 ASCYLIB/TPC-C/ISL/HSL traces | 772247503320 | 131485775944 |
| 40 HNSW traces | 491146472840 | 70372567718 |
| 20 Valkey traces | 165020548120 | 30898649553 |
| 40 HSL databases, separate from traces | 76653882709 | 40184798665 |
| Total | 1505068406989 | 272941791880 |

The compressed total alone is **254.2 GiB**. As an initial provisioning budget,
allow **at least 400 GiB for archives and 100 GiB free on the live trace/database
filesystem**, plus separate space for source/build trees, container images,
failed attempts, and independent backups. These are planning budgets, not upper
bounds: compression, runtime record production and existing data vary. Keeping
all uncompressed successful data would require about 1.51 TB before those extras.

The original workflow enforced a 50-GiB free-space floor on each filesystem,
reserved each trial's worst-case output before launch, wrote measured traces
and databases to NFS, and compressed only between trials. It independently
decompressed and hashed archives and published durable receipts before deleting
exact successful raw files. It never automatically deleted compressed archives.
Changing storage can change logging overhead. Scratch archives are not an
independent backup. Large traces/databases are not bundled in this source archive;
the JSON preserves per-cell source hashes and historical paths as provenance,
not locally accessible files or a claim to re-audit their bytes here.
