# Matched backend spatial-by-temporal ablation

September 29, 2026. All 32 runs completed: one discarded warmup and three
interleaved measured trials per cell on each of two inputs. Complete prepared
payload hashes match across all 16 runs within each input.

## Paper table

| Spatial range updates | Temporal prefix sums | Valkey cache / preparation (s) | BCCO cache / preparation (s) |
| --- | --- | ---: | ---: |
| No | No | 100.77 / 105.99 | 6.51 / 10.25 |
| Yes | No | 13.35 / 18.63 | 5.58 / 9.37 |
| No | Yes | 5.85 / 11.06 | 19.97 / 23.72 |
| Yes | Yes | 3.61 / 8.90 | 7.01 / 10.81 |

Caption: Cache preparation / complete backend preparation in seconds; medians of three interleaved trials per variant. All variants use the same retained inputs, 2,000 time buckets, 128-page and 100,000-history-record budgets, and fixed clustering seed. Complete preparation includes database reading, statistics, page preparation, cache preparation, and JSON serialization; it excludes HTTP and browser rendering. Output hashes match within each input.

## Interpretation

- valkey: enabling both techniques changes cache preparation from 100.773 to 3.609 s (baseline/optimized ratio 27.92), and complete preparation from 105.988 to 8.899 s (ratio 11.91). Ratios below one mean the optimized combination is slower.
- bcco: enabling both techniques changes cache preparation from 6.511 to 7.014 s (baseline/optimized ratio 0.93), and complete preparation from 10.249 to 10.814 s (ratio 0.95). Ratios below one mean the optimized combination is slower.

Compare rows within a fixed setting of the other factor to attribute an
individual technique. Do not multiply speedups from different comparisons.
In particular, examine range-only versus both on BCCO: short lifetimes can
make direct temporal accumulation cheaper than prefix sums.

## Trial ranges and memory

| Input | Spatial / temporal | Cache min–max (s) | Preparation min–max (s) | Median peak RSS (MiB) |
| --- | --- | ---: | ---: | ---: |
| valkey | enumerated / direct | 85.125–103.072 | 90.328–108.355 | 1888.4 |
| valkey | range / direct | 13.122–13.548 | 18.274–18.850 | 1890.1 |
| valkey | enumerated / prefix | 5.719–6.020 | 10.894–11.350 | 2127.7 |
| valkey | range / prefix | 3.522–3.692 | 8.840–8.951 | 2127.9 |
| bcco | enumerated / direct | 6.462–6.605 | 10.244–10.375 | 1869.1 |
| bcco | range / direct | 5.550–5.670 | 9.344–9.435 | 1869.2 |
| bcco | enumerated / prefix | 19.943–20.509 | 23.708–24.280 | 2077.2 |
| bcco | range / prefix | 6.959–7.046 | 10.789–10.827 | 2077.7 |

## Method and provenance

All cells use fresh isolated Linux workers on the local i7-14700KF/WSL2 host,
two CPU equivalents, 12 GiB, and one BLAS/OpenMP thread. No GPU participates
in this backend experiment. Cache geometry is 32 KiB, eight-way, with 64-byte
lines; database page sizes are 4 KiB for Valkey and 2 MiB for BCCO. The seed
is 20260929. Prepared history reduction, field expansion, reconstruction, and
the complete output format are unchanged across cells. Sources and input
hashes are frozen in the evidence manifest.

The enumerated reference uses NumPy add.at with repeated cache-set indices.
Its direct-temporal form broadcasts updates across a NumPy lifetime slice;
it has no Python loop over time buckets. Unlike the older spatial ablation,
it omits redundant per-line bucket/type index arrays, so this is a streamlined
reference rather than byte-for-byte historical code. The same helper is used
with and without temporal prefix sums.

Self-tests include 1,000 random spatial comparisons and 503 temporal/oracle
cases for each spatial helper. Full-payload equality also holds on both real
inputs across every cell and repeat. Cache phases are limited to 150 s,
workers to 180 s, and launching further trials to a 30-minute campaign.
No measured trial was censored.

Raw results: [backend-matrix-results-20260929.json](backend-matrix-results-20260929.json).
Summary: [backend-matrix-summary-20260929.json](backend-matrix-summary-20260929.json).
LaTeX table: [backend-matrix-table.tex](backend-matrix-table.tex).
Author-local frozen sources, controller records, manifests, and trial logs:
`artifact-tools/backend-matrix-20260929/` in the parent workspace.

See [paper prose and interface table](PAPER_PROCESSING_OPTIMIZATIONS.md). Earlier
standalone ablations remain preserved; this matched matrix supersedes them
for joint spatial/temporal attribution.
