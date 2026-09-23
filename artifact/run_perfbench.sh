#!/usr/bin/env bash
# Compatibility wrapper: the unified runner covers all nine before/after groups.
# Invoke inside the dependency container. Default smoke, explicit --profile paper.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" == --quick ]]; then shift; set -- --profile smoke "$@"; fi
exec python3 "$ROOT/artifact/ae.py" all-performance "$@"
