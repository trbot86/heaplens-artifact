# Pyke headless UI feasibility smoke

September 29, 2026. This is a short environment/interaction smoke, not a repeated
ablation or a completed database-loading experiment. Evaluator-facing checkouts
and installed packages were not changed.

## Outcome

Pyke can run the current optimized UI in a modern, headless browser without an
X/Wayland session. The one discarded warmup and both measured cases completed
all interaction assertions without uncaught page errors or automatic downloads.
Screenshots were inspected. Both test services were stopped, and no user-owned
Chromium process remained afterward.

The environment differs materially from the local workstation: Pyke uses
software compositing/rasterization, whereas a fresh diagnostic of the local
headless Edge configuration reports GPU acceleration on an NVIDIA RTX 3080.
Use Pyke for same-host controlled comparisons, not as an interchangeable source
of desktop absolute latency figures.

## Environment and rendering diagnostics

- Pyke: dual Intel Xeon Gold 5220R, 48 physical/96 logical CPUs, 186 GiB RAM;
  Linux 6.8.0-137-generic. Load averages were 0.00 before setup, with approximately
  181 GiB available. No active application-benchmark load was observed, and no
  Docker container was running.
- Installed Chromium: `153.0.8010.47` (Snap); V8 `15.3.76.12`.
  Neither `DISPLAY` nor `WAYLAND_DISPLAY` was set for the SSH session.
- Hardware inspection: ASPEED display controller; `/dev/dri/card0`, but no
  render node found. Browser diagnostics, rather than this inventory alone,
  establish the rendering mode used in the smoke.
- Chromium CDP: GPU compositing and rasterization report `disabled_software`.
  A WebGL context is available and identifies ANGLE/SwiftShader (software).
  Thirty idle animation-frame intervals were approximately 16.6-16.8 ms.
  This is callback scheduling, not measurement of an attached display.
- Comparison diagnostic on the Windows workstation: Edge `154.0.4258.37`,
  V8 `15.4.11.5`, ANGLE/D3D11 on NVIDIA RTX 3080; GPU compositing and rasterization
  enabled. CPU, OS, browser/V8 version, and graphics configuration all differ;
  do not attribute cross-host timing differences solely to the GPU.
- Artifact-pinned Next.js 14.2.8 and Node 18.18.2 in the existing Docker image
  `heaplens-ae-t35brown:20260927-dvy-portable`. UI container: four CPUs/8 GiB;
  fixture service: two CPUs/2 GiB. Both ports were bound to host loopback only.
- Playwright Core 1.62.1 used a private Node 20.20.2 binary extracted from the
  already-present `node:20-bookworm-slim` image. The system Node was not upgraded.
- Browser runs on the host, not inside either container; no browser CPU pinning
  or custom JS heap limit was applied. Viewport 1440x1000, device scale factor 1.
  The browser launcher uses Playwright's normal headless arguments. Record and
  hold resources/browser flags fixed before a formal repeated study.

Modern Chrome headless uses the regular browser implementation without displaying
its platform windows; see [Chrome's official headless documentation](https://developer.chrome.com/docs/automation-and-testing/headless).
The smoke directly verifies that this Pyke installation can render and interact
with HeapLENS, rather than inferring support from browser version alone.

## Inputs and measurements

Reused the exact prepared synthetic fixtures from the local study. They contain
32-byte live objects, plus fixed retained BCCO cache/statistics panels. Those
panels are controls, not statistics recomputed from the synthetic objects.
Database preparation and fixture generation are excluded. HTTP transfer, JSON
decoding, initialization, and initial rendering are included in ready time.
The fixture payloads are 72,393,313 bytes and 67,559,263 bytes respectively.

The route was compiled before collection; one full `live100k` warmup was excluded.
Each measured case then used a fresh browser. Interaction values are within-trial
medians of input-handler entry to the second animation-frame callback, not actual
compositor presentation or remote-desktop latency. There is only **one measured
trial per case**; these values have no cross-trial uncertainty estimate.

| Operation | 128 pages / 100k: local* | 128 pages / 100k: Pyke | Dense page / 65,536: local | Dense page / 65,536: Pyke |
|---|---:|---:|---:|---:|
| Navigation to ready | 1.320 s | 3.784 s | 1.191 s | 2.455 s |
| Timeline pointer movement | 108 ms | 289 ms | 22 ms | 54 ms |
| Page-type visibility toggle | 336 ms | 612 ms | 46 ms | 152 ms |
| Cache-type visibility toggle | 255 ms | 385 ms | 43 ms | 95 ms |
| Type filter / clear | 65 ms | 136 ms | 35 ms | 71 ms |
| Scroll wheel | 17 ms | 23 ms | 17 ms | 17 ms |
| Select a populated 68-KiB region | Not applicable | Not applicable | 0.417 s | 1.177 s |

Local values are medians across three trials; Pyke values come from one trial.
The dense-page comparison uses the same optimized source and default browser
heap policy. *The local 128-page values are from the earlier three-trial study,
before the detail-rendering optimization, with a 2-GiB JS heap limit. The listed
128-page operations occur before detail selection, but this is nevertheless an
approximate comparison, not a fully matched cross-host experiment. Excluded
warmup observations are not substituted for measured trials.

Sources: `large-ui-results-20260928.json` for local `live100k`,
`detail-ablation-results-20260929.json` (optimized) for local `dense64k`, and the
Pyke smoke's `summary.json`. For the cleaner dense-page comparison, Pyke takes
about 2.1-3.3 times as long for loading, timeline changes, visibility changes,
and populated detail selection; scrolling is approximately unchanged. These
ratios do not isolate the effect of GPU acceleration.

The 128-page gesture selects an empty part of its relatively sparse first page;
its 595-ms response must not be described as dense object-detail rendering.
The dense-page selection displays 2,176 object rectangles plus two clip
rectangles. Both cases also passed zoom-in/out state assertions. No renderer
crash, page error, or unexpected export occurred.

For orientation only, the prior local optimized dense-page study had a
three-trial median of 1.191 s to ready and 0.417 s for the same populated region
selection. The new single Pyke observation is not a controlled cross-host or
GPU ablation. It shows that the operation works but can be visibly slower.

## Setup issue, scope, and next use

The initial attempt failed before the app loaded: running npm as the unprivileged
test UID tried to create `/.npm`. No latency from that attempt is used. The
corrected launcher invokes the installed Next.js entrypoint directly with Node
and waits for readiness. No permission changes or system-level installs were
needed. The original failed attempt remains in `evidence/`; successful evidence
is in `evidence-v2/`.

Pyke is viable for backend/conversion measurements and for explicitly labeled
software-rendered browser ablations. For desktop usability claims, retaining
local GPU-backed browser measurements is useful. Another valid arrangement is
a Pyke backend with a local browser, but end-to-end loading would then include
network/tunnel cost and must be measured/labeled separately. No such hybrid
measurement was performed here.

Before a formal Pyke browser comparison, use the same browser binary, fixtures,
viewport, headless arguments, CPU/memory policy, and warmup for all variants;
repeat interleaved pairs and verify visible equivalence. Do not mix Pyke baseline
times with local optimized times. The broader processing ablation campaign has
not been launched as part of this smoke.

## Evidence and replay

- Remote isolated directory: `/tmp/heaplens-pyke-ui-20260929-GgjCqH`.
- Local author evidence: `artifact-tools/pyke-ui-smoke-20260929/` in the enclosing
  workspace, including `summary.json`, `local-browser-rendering.json`, and the
  extracted `evidence-v2/` browser logs, rendering diagnostics, and screenshots.
- Fixture SHA-256: `live100k.json`
  `fc781dcec3a8a7cbb75fadf26cd3e538d9f15933abd876f13f57bf20545b0a9b`;
  `dense64k.json`
  `740dec40c159e9821d5fe0d3eadd3174308ec7c0337c695635fe7daf700985e5`.
- Tested `pagesComponent.tsx` SHA-256:
  `e8af9d952ff0767e563a9e251384d2d6b86e2ea5d774b4993b81cee92b1550ca`;
  `detailEvents.ts`:
  `f810fc97219fd9b262ecc093e39eec01db49f22c06fc9b0fad1017f280c80d60`.
  These match the locally tested optimized files. The disposable UI retains the
  same test-only initial 2-MiB page-size selection as the previous local study.
- `probe_browser_rendering.cjs` records browser/CDP rendering details separately
  from timing. `run_pyke_ui_smoke.sh` is the dated smoke launcher; it expects the
  prepared private bundle and unused container names. Reuse the protocol with a
  fresh directory/names for another run, not the completed evidence folders.
- `benchmark_large_ui.cjs` supplies the interaction checks. Its per-trial status
  is checked explicitly because it records failed trials without itself returning
  a failure exit code. `summarize_large_ui.cjs` excludes the warmup and records
  the actual trial count, including for this single-trial smoke.
- First browser-probe deadline 30 s; UI batch deadline 240 s; outer launcher
  deadline 360 s. All successful checks completed within those limits. Test
  containers are stopped, retained for inspection; no evaluator code was changed.
