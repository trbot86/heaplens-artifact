#!/usr/bin/env bash
# Run from Linux/WSL. Mount only this artifact; never requires host admin changes.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${HEAPLENS_IMAGE:-heaplens-atc26:submission}"
if [[ "${1:-}" == build ]]; then
    exec docker build -f "$ROOT/artifact/Dockerfile" -t "$IMAGE" "$ROOT"
fi
if [[ $# == 0 ]]; then
    echo 'Usage: bash artifact/run.sh build|doctor|history|smoke|export|gui|hnsw|hnsw-factorization|valkey|rocksdb|experiment|all-performance [options]'
    exit 2
fi
extra=()
if [[ "$1" == gui ]]; then extra=(-p 127.0.0.1:3000:3000 -p 127.0.0.1:5000:5000); fi
# Optional narrowly scoped permissions for NUMA/perf on dedicated Linux hosts.
# Smoke/GUI/export do not need these. Never pass --privileged by default.
if [[ "${HEAPLENS_NUMA:-0}" == 1 ]]; then extra+=(--security-opt seccomp=unconfined); fi
if [[ "${HEAPLENS_PERF:-0}" == 1 ]]; then extra+=(--cap-add PERFMON); fi
exec docker run --rm -i --init "${extra[@]}" -e NEXT_TELEMETRY_DISABLED=1 \
    -e HEAPLENS_CACHE_BUDGET_MB="${HEAPLENS_CACHE_BUDGET_MB:-4096}" \
    -e PERFBENCH_PERF="${PERFBENCH_PERF:-on}" \
    -v "$ROOT:/root/sifter" -w /root/sifter "$IMAGE" python3 artifact/ae.py "$@"
