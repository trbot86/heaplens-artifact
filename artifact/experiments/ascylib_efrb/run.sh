#!/usr/bin/env bash
# HeapLENS paper Table 1 row 1 / Section 6.2 / Figures 4-5: EFRB tree
# (Ellen, Fatourou, Ruppert, van Breugel) from ASCYLIB.
# See artifact/lib/ascylib_experiment.sh for exact scope (diagnostic only).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/ascylib_experiment.sh"
run_ascylib_experiment "src/bst-ellen" "lf-bst_ellen" "ascylib_efrb" STM=LOCKFREE
