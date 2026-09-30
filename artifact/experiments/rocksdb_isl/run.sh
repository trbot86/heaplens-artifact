#!/usr/bin/env bash
# Trace the same historical source and tall-node flags as the performance driver.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/rocksdb_experiment.sh"
run_rocksdb_experiment rocksdb_isl
