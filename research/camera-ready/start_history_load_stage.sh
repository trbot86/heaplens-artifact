#!/usr/bin/env bash
# Run only after paired UI timings finish. Reuse their optimized frontend.
set -euo pipefail
workspace=/mnt/c/Users/trbot/Documents/ChatGPT/atc2026
study=/tmp/heaplens-processing-ablation-20260929
source="$workspace/artifact-camera-ready/research/camera-ready"
mkdir -p "$study/candidate/research/load-stage"
cp "$source/ablate_histories.py" "$source/serve_history_ablation.py" "$study/candidate/research/load-stage/"
sha256sum "$study/candidate/research/load-stage/"*.py > "$study/evidence/load-stage-source.sha256"
docker stop -t 3 heaplens-detail-baseline-20260929 heaplens-large-http-20260928
docker run --name heaplens-history-load-20260929 --init -d --cpus 2 --memory 12g --pids-limit 128 \
  --read-only --tmpfs /tmp:rw,size=1g -p 127.0.0.1:5000:5000 \
  -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 -e PYTHONDONTWRITEBYTECODE=1 -e MPLCONFIGDIR=/tmp/mpl \
  -v "$study/candidate:/candidate:ro" -v "$study/inputs:/inputs:ro" -v "$study/evidence:/evidence" \
  --entrypoint python3 heaplens-atc26:submission \
  /candidate/research/load-stage/serve_history_ablation.py --root /candidate
timeout 45s bash -c 'until curl -fsS --max-time 2 http://127.0.0.1:5000/health; do sleep 1; done'
