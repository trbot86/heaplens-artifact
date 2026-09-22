#!/usr/bin/env bash
# HeapLENS paper Table 1 row 3 / Appendix B: HJ tree (Howley, Jones) from
# ASCYLIB.
# See artifact/lib/ascylib_experiment.sh for exact scope (diagnostic only).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/ascylib_experiment.sh"
run_ascylib_experiment "src/bst-howley" "lf-bst-howley" "ascylib_hj" STM=LOCKFREE
