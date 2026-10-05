# Pipeline and UI validation — October 5, 2026

The packaged frozen-source backend and both browser commands completed end to end.
Separate current-camera-ready checks also completed. These observations preserve
the paper's original reference results; they do not replace or pool with them.

```bash
python3 artifact/camera-ready-reproduction/validation-20261005/verify.py
```

The verifier checks evidence hashes, completeness, output/selection checks and
recomputes every median below from individual trial rows. All six studies
completed cleanup. Backend studies ran serially before the browser studies.

## Backend preparation

Seconds; medians of three trials. Each frozen variant also has one discarded
warmup per input: 32 total cells. The current production range/prefix code has
two warmups plus six measured cells. Native log conversion, HTTP transfer and
browser work are excluded.

| Input | Spatial / temporal | Frozen cache / complete preparation (s) |
| --- | --- | ---: |
| valkey | enumerated / direct | 98.220 / 103.563 |
| valkey | range / direct | 13.535 / 18.917 |
| valkey | enumerated / prefix | 5.803 / 11.178 |
| valkey | range / prefix | 3.528 / 8.893 |
| bcco | enumerated / direct | 6.665 / 10.590 |
| bcco | range / direct | 5.681 / 9.573 |
| bcco | enumerated / prefix | 19.911 / 23.834 |
| bcco | range / prefix | 7.059 / 10.937 |

| Current checkout input | Cache (s) | Complete preparation (s) |
| --- | ---: | ---: |
| valkey | 3.602 | 9.214 |
| bcco | 7.197 | 11.182 |

Complete-payload hashes match across all repetitions/variants within each
frozen input, and within each current input. Frozen payload hashes also match
the historical reference; current cache hashes match the frozen version.
Current source adds object-extent metadata, so whole-payload hashes are not a
cross-version equality criterion. For BCCO, the combined implementation remains
slower than the baseline.

## Browser response

Milliseconds; medians of three trial medians. The frozen toggle study has 18
contexts, with paired rendered-state and text-export equality. All 18 frozen
trials also match their historical rendered states and exports. The current
toggle study has nine contexts with page-count, error and timing checks.

| Cache visibility input | Frozen baseline | Frozen optimized | Current |
| --- | ---: | ---: | ---: |
| valkey-full, 52 pages | 817.85 | 80.70 | 89.50 |
| tpcc-bcco-2m, 17 pages | 487.50 | 53.45 | 56.25 |
| tpcc-bcco-2m, 128 pages | 1027.20 | 252.30 | 255.70 |

| Select 65,536 bytes | Frozen baseline | Frozen optimized | Current |
| --- | ---: | ---: | ---: |
| dense64k | 19257.50 | 370.20 | 373.40 |
| dense1m | 21120.80 | 403.20 | 409.70 |
| live1m | 3079.00 | 1148.40 | 1144.70 |

The detail studies completed 18 frozen and nine current fresh-browser trials,
plus two/one discarded warmups. Every measured selection is exactly 65,536
bytes. The optimized/current view has 2,048 object rectangles plus two clipping
rectangles; frozen baselines have 65,536 or 7,813 object rectangles. No page
errors were reported. Current studies test only the current implementation;
their values are standalone observations rather than new speedup estimates.

## Environment and limits

Intel i7-14700KF; Windows/WSL2 Docker; two CPU equivalents, 12 GiB and one
BLAS/OpenMP thread per backend worker. The unchanged image ID is recorded in
each image receipt. Node 24.14.0, Playwright Core 1.62.1, headless Edge
154.0.4258.53 and RTX 3080 acceleration. GPU/compositing probes accompany every
browser study. The original reference used Edge 154.0.4258.37. Existing unrelated
services remained running; this was not a recreated idle-machine environment.
For example, the 128-page BCCO toggle is slower here than the saved reference
(1.027 / 0.252 s here versus 0.571 / 0.137 s previously). This check verifies
reproduction of the intended views and comparisons, not identical absolute
timings. It does not establish the cause of that timing difference.

The current production source came from camera-ready commit `207e45921ab536b96e49dc3ec89dd8fc9a446865`;
no production algorithms changed during this validation. Current-source hashes
and effective UI hashes accompany the rows. Compressed effective-source snapshots
and the controller versions used are bundled for byte-level provenance, including
line endings. They are archival copies; use the main reproduction commands to run
the studies. Private copies used ports 3180–3183/5180 and the fixed BCCO fixture's 2-MiB initial page size. These
configuration adapters are recorded; the checkout and frozen archives were
not edited by a run. The current backend test adapter adds a zero-valued
actualSize field to synthetic legacy rows, outside timed production work.

UI timings run to a second animation-frame callback, not physical display
presentation. Payload replay excludes backend work. Native log conversion
and application-to-screen time were not measured here; do not sum separate
backend/UI observations into an end-to-end timing. Three trials describe this
check and do not establish confidence bounds or performance guarantees.

All original evidence, failed preflight attempts, source snapshots and archives
remain preserved. No full application/overhead/sampling campaign was rerun.
The paper and its saved numerical references were unchanged.
