#!/usr/bin/env bash
# Isolated short capability smoke; no evaluator checkout or system setup edits.
set -euo pipefail
study=${1:?Pass the previously created private /tmp study directory}
case "$study" in /tmp/heaplens-pyke-ui-20260929-*) ;; *) exit 2;; esac
test -d "$study"
test "$(stat -c %u "$study")" = "$(id -u)"
cd "$study"
mkdir -p evidence-v2
mkdir -p sifter_vis_d3/sifter
tar -xzf ui.tar.gz -C sifter_vis_d3/sifter
image=heaplens-ae-t35brown:20260927-dvy-portable
ui_name=heaplens-pyke-ui-smoke-20260929-v2
api_name=heaplens-pyke-api-smoke-20260929-v2
cleanup() {
  docker logs "$ui_name" > evidence-v2/ui-server.log 2>&1 || true
  docker logs "$api_name" > evidence-v2/api-server.log 2>&1 || true
  docker stop -t 3 "$ui_name" "$api_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
# Private recent Node binary for the Playwright driver; use the artifact's
# pinned Node/dependencies for the application itself. No global installation.
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$study:/study" --entrypoint cp node:20-bookworm-slim /usr/local/bin/node /study/node
./node --version
ldd ./node
export HEAPLENS_PLAYWRIGHT="$study/node_modules/playwright-core"
export HEAPLENS_BROWSER=/snap/bin/chromium
export HEAPLENS_PROBE_OUTPUT="$study/evidence-v2/browser-rendering.json"
timeout --signal=TERM --kill-after=3s 30s ./node \
  research/camera-ready/probe_browser_rendering.cjs \
  > evidence-v2/browser-probe.log 2>&1
test -L sifter_vis_d3/sifter/node_modules || \
  ln -s /opt/heaplens-ui/node_modules sifter_vis_d3/sifter/node_modules
docker run --name "$api_name" --init -d --cpus 2 --memory 2g --pids-limit 128 \
  -p 127.0.0.1:5000:5000 -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$study:/study:ro" --entrypoint python3 "$image" \
  /study/research/camera-ready/serve_large_ui_fixtures.py --output /study
docker run --name "$ui_name" --init -d --cpus 4 --memory 8g --pids-limit 256 \
  --user "$(id -u):$(id -g)" -p 127.0.0.1:3008:3000 -e NEXT_TELEMETRY_DISABLED=1 \
  -v "$study/sifter_vis_d3/sifter:/ui" -w /ui --entrypoint node "$image" \
  /opt/heaplens-ui/node_modules/next/dist/bin/next dev --hostname 0.0.0.0
# Exclude route compilation and the asynchronous server startup from trials.
timeout --signal=TERM --kill-after=3s 75s bash -c \
  'until curl -fsS --max-time 10 -o /dev/null http://127.0.0.1:3008/vispanels; do sleep 1; done'
export HEAPLENS_EVIDENCE="$study/evidence-v2"
export HEAPLENS_UI_PORT=3008
export HEAPLENS_CASES='["live100k","dense64k"]'
export HEAPLENS_REPS=1
export HEAPLENS_JS_HEAP_MB=default
timeout --signal=TERM --kill-after=5s 240s ./node \
  research/camera-ready/benchmark_large_ui.cjs > evidence-v2/browser-run.log 2>&1
pgrep -afu "$(id -u)" chromium > evidence-v2/browser-processes-after.txt || true
# The reused browser harness retains per-trial failures without setting its
# process exit status. Require all three final records (including warmup).
./node -e 'const fs=require("fs"); const rows=fs.readFileSync("evidence-v2/browser.jsonl","utf8").trim().split("\n").map(JSON.parse).filter(x=>x.checkpoint==="final"); if(rows.length!==3||rows.some(x=>x.status!=="complete"||x.errors.length))process.exit(1); console.log("All three browser smoke trials completed without page errors.")'
