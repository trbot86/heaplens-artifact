#!/usr/bin/env bash
# HeapLENS paper Table 1 row 2 / Appendix B: DVY tree (Drachsler, Vechev,
# Yahav) from ASCYLIB.
# See artifact/lib/ascylib_experiment.sh for exact scope (diagnostic only).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/ascylib_experiment.sh"
run_ascylib_experiment "src/bst-drachsler" "lb-bst-drachsler" "ascylib_dvy"
# (bst-drachsler's default build takes no STM=... flag, unlike bst-ellen/bst-howley)
