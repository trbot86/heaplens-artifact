#!/usr/bin/env bash
# HeapLENS paper Section 6.2 / Figure 5 / Table 1 row 1: EFRB tree (Ellen,
# Fatourou, Ruppert, van Breugel) from ASCYLIB, comparing stock allocation
# against the paper's two fixes for cache set underutilization by tree
# nodes: multithreaded prefilling (perturbs the deterministic allocation
# pattern that causes underutilization) and separate memory arenas for
# nodes vs. operation descriptors (the "more principled" fix). This is the
# quantitative "before/after" ablation -- contrast with
# artifact/experiments/ascylib_efrb, which runs the HeapLENS instrumentation/
# sampling pipeline on the stock tree to produce a .sqlite database for the
# visualizer.
#
# Ported and cleaned up from ASCYLIB_exp/ASCYLIB/run_experiment_asplos.sh's
# "ellen" variants (Default_ellen / Obj_seg_ellen / MTprefill_ellen /
# Both_ellen), which together cover Figure 5's three panels (a=Default,
# b=+prefill, c=+prefill+arenas="Both") plus the "arenas alone" variant
# (Obj_seg) needed to attribute the two fixes' individual contributions.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIFTER_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$SIFTER_ROOT/artifact/lib/ascylib_perfbench.sh"

# Confirmed revised-paper setting: four physical cores, search-only for
# five seconds, 2^18 initial keys, and node-local interleave as in the
# retained historical script. Diagnostic/overhead trace settings are separate.
THREADS="${THREADS:-4}"
export PERFBENCH_MEMORY="${PERFBENCH_MEMORY:-interleave}"
INITIAL="${INITIAL:-262144}"   # 2^18
RANGE="${RANGE:-524288}"       # ASCYLIB convention: 2x initial
DURATION_MS="${DURATION_MS:-5000}"
UPDATE_PCT="${UPDATE_PCT:-0}"  # search-only
REPS="${REPS:-3}"              # paper used 10; override for full fidelity

OUT_NAME="ascylib_efrb_bench"
RESULTS_TSV="$SIFTER_ROOT/artifact/experiments/$OUT_NAME/results.tsv"
RUN_DIR="$SIFTER_ROOT/artifact/experiments/$OUT_NAME/runs"

echo "=== [$OUT_NAME] fresh working copy of ASCYLIB ==="
ascylib_perfbench_setup "$OUT_NAME"
perfbench_init_results "$RESULTS_TSV"
rm -rf "$RUN_DIR"

run_variant() {
    local label="$1"; shift
    echo "=== [$OUT_NAME] $label ==="
    ascylib_perfbench_build "src/bst-ellen" STM=LOCKFREE SET_CPU=0 "$@"
    ascylib_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "$label" "lf-bst_ellen" \
        "$THREADS" "$INITIAL" "$RANGE" "$UPDATE_PCT" "$DURATION_MS" "$REPS"
}

run_variant "a_default"
run_variant "b_obj_seg" SEG_OBJS=1
run_variant "c_mt_prefill" INIT=all
run_variant "d_both" SEG_OBJS=1 INIT=all

perfbench_run_campaign "$RESULTS_TSV" "$RUN_DIR"

perfbench_print_summary "$RESULTS_TSV" "ASCYLIB EFRB tree: default -> +obj segregation / +MT prefill / +both (paper Section 6.2 / Figure 5 / Table 1 row 1)" \
    "$SIFTER_ROOT/artifact/experiments/$OUT_NAME/summary.txt"
