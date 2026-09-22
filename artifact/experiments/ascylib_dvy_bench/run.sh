#!/usr/bin/env bash
# HeapLENS paper Appendix B.1 / Table 3: DVY tree (Drachsler, Vechev, Yahav)
# from ASCYLIB, comparing throughput/miss-rates across four node padding
# levels: 96B (ASCYLIB's default padding), 72B (no padding), 128B, and
# 192B. The paper's finding is non-monotonic: 128B (exactly two cache
# lines) is the worst choice due to cache set underutilization, while 192B
# (three full cache lines) wins despite the extra space overhead. This is
# the quantitative "before/after" ablation -- contrast with
# artifact/experiments/ascylib_dvy, which runs the HeapLENS instrumentation/
# sampling pipeline on the stock (96B) tree to produce a .sqlite database
# for the visualizer.
#
# Ported and cleaned up from ASCYLIB_exp/ASCYLIB/run_experiment_asplos.sh's
# "drachsler" variants (Default_pad_drachsler / No_pad_drachsler /
# 128B_pad_drachsler / 192B_pad_drachsler).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIFTER_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$SIFTER_ROOT/artifact/lib/ascylib_perfbench.sh"

# Appendix B methodology: 8 threads, search-only workload, tree initially
# containing 2^20 keys.
THREADS="${THREADS:-8}"
INITIAL="${INITIAL:-1048576}"  # 2^20
RANGE="${RANGE:-2097152}"      # ASCYLIB convention: 2x initial
DURATION_MS="${DURATION_MS:-5000}"
UPDATE_PCT="${UPDATE_PCT:-0}"  # search-only
REPS="${REPS:-3}"              # paper used 10; override for full fidelity

OUT_NAME="ascylib_dvy_bench"
RESULTS_TSV="$SIFTER_ROOT/artifact/experiments/$OUT_NAME/results.tsv"
RUN_DIR="$SIFTER_ROOT/artifact/experiments/$OUT_NAME/runs"

echo "=== [$OUT_NAME] fresh working copy of ASCYLIB ==="
ascylib_perfbench_setup "$OUT_NAME"
perfbench_init_results "$RESULTS_TSV"
rm -rf "$RUN_DIR"

run_variant() {
    local label="$1"; shift
    echo "=== [$OUT_NAME] $label ==="
    # bst-drachsler's default build takes no STM=... flag, unlike
    # bst-ellen/bst-howley. VERSION=O2 matches the paper's own experiments.
    ascylib_perfbench_build "src/bst-drachsler" VERSION=O2 "$@"
    ascylib_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "$label" "lb-bst-drachsler" \
        "$THREADS" "$INITIAL" "$RANGE" "$UPDATE_PCT" "$DURATION_MS" "$REPS"
}

run_variant "a_96B_default"
run_variant "b_72B_no_pad" DRACHSLER_PAD=0
run_variant "c_128B_pad" DRACHSLER_PAD=128
run_variant "d_192B_pad" DRACHSLER_PAD=192

perfbench_print_summary "$RESULTS_TSV" "ASCYLIB DVY tree: node padding 96B/72B/128B/192B (paper Appendix B.1 / Table 3)" \
    "$SIFTER_ROOT/artifact/experiments/$OUT_NAME/summary.txt"
