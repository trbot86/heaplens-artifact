#!/usr/bin/env bash
# HeapLENS paper Table 1 row 4 / Section 6.3: TPC-C with the BCCO tree
# (Bronson, Casper, Chafi, Olukotun) as the database index.
# See artifact/lib/tpcc_experiment.sh for exact scope (diagnostic only).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/tpcc_experiment.sh"
run_tpcc_experiment "bronson_pext_bst_occ" "tpcc_bcco"
