#!/usr/bin/env bash
# Paper Section 6.4: use the restored experimental source, not no-op flags.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/rocksdb_perfbench.sh"
run_rocksdb_perfbench skip_list "$@"
