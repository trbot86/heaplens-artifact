#!/usr/bin/env bash
# Compatibility names delegate to the single, source-checked historical driver.
# Run in the dependency container; see artifact/README.md for profiles.
set -euo pipefail
run_rocksdb_perfbench() {
    local root
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    local memtable="$1"; shift
    local args=(--profile "${PROFILE:-smoke}" --jobs "${BUILD_JOBS:-4}")
    if [[ -n "${REPS:-}" ]]; then args+=(--reps "$REPS"); fi
    if [[ -n "${KEY_SIZE:-}" ]]; then args+=(--rocks-key-size "$KEY_SIZE"); fi
    if [[ -n "${VALUE_SIZE:-}" ]]; then args+=(--rocks-value-size "$VALUE_SIZE"); fi
    exec python3 "$root/artifact/ae.py" rocksdb --memtable "$memtable" "${args[@]}" "$@"
}
