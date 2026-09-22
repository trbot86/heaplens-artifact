#!/usr/bin/env bash
# HeapLENS paper Section 6.4: RocksDB's HashSkipList memtable, at the commit
# immediately preceding the paper's fix (PR #13424 / commit 0c7e5bd, which
# shrank the per-bucket SkipList object from 56B to 48B).
# See artifact/lib/rocksdb_experiment.sh for exact scope (diagnostic only)
# and known open risks (not yet run end-to-end).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/rocksdb_experiment.sh"
run_rocksdb_experiment
