#!/usr/bin/env bash
# HeapLENS paper Appendix B.2 / Table 4: Howley & Jones (HJ) tree from
# ASCYLIB, comparing throughput/miss-rates when ASCYLIB's internal
# sub-allocator (ssalloc) is backed by glibc's malloc vs. jemalloc. This is
# the quantitative "before/after" ablation -- contrast with
# artifact/experiments/ascylib_hj, which runs the HeapLENS
# instrumentation/sampling pipeline on the stock tree to produce a .sqlite
# database for the visualizer.
#
# Ported and cleaned up from ASCYLIB_exp/ASCYLIB/run_experiment_asplos.sh's
# "howley" variants (glibc_malloc_howley / jemalloc_howley).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIFTER_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$SIFTER_ROOT/artifact/lib/ascylib_perfbench.sh"

# Confirmed revised-paper setting: 24 physical cores, search-only workload,
# 2^20 initial keys. The earlier eight-thread setting remains selectable.
THREADS="${THREADS:-24}"
INITIAL="${INITIAL:-1048576}"      # 2^20
RANGE="${RANGE:-2097152}"          # ASCYLIB convention: 2x initial
DURATION_MS="${DURATION_MS:-5000}"
UPDATE_PCT="${UPDATE_PCT:-0}"      # search-only
REPS="${REPS:-3}"                  # paper used 10; override for full fidelity

OUT_NAME="ascylib_hj_bench"
RESULTS_TSV="$SIFTER_ROOT/artifact/experiments/$OUT_NAME/results.tsv"
RUN_DIR="$SIFTER_ROOT/artifact/experiments/$OUT_NAME/runs"
case "${HJ_JEMALLOC:-5.3}" in
    5.3) JEMALLOC_LIB="$SIFTER_ROOT/artifact/vendor/heaplens-allocators/libjemalloc-heaplens.so" ;;
    5.0) JEMALLOC_LIB="$SIFTER_ROOT/artifact/vendor/setbench/lib/libjemalloc.so" ;;
    *) echo "HJ_JEMALLOC must be 5.3 or 5.0" >&2; exit 2 ;;
esac
test -s "$JEMALLOC_LIB"

echo "=== [$OUT_NAME] fresh working copy of ASCYLIB ==="
ascylib_perfbench_setup "$OUT_NAME"
perfbench_init_results "$RESULTS_TSV"
rm -rf "$RUN_DIR"

echo "=== [$OUT_NAME] building HJ tree ==="
ascylib_perfbench_build "src/bst-howley" STM=LOCKFREE SET_CPU=0

echo "=== [$OUT_NAME] glibc_malloc_howley ==="
ascylib_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "glibc_malloc" "lf-bst-howley" \
    "$THREADS" "$INITIAL" "$RANGE" "$UPDATE_PCT" "$DURATION_MS" "$REPS"

echo "=== [$OUT_NAME] jemalloc_howley ==="
ascylib_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "jemalloc" "lf-bst-howley" \
    "$THREADS" "$INITIAL" "$RANGE" "$UPDATE_PCT" "$DURATION_MS" "$REPS" \
    "$JEMALLOC_LIB"

perfbench_run_campaign "$RESULTS_TSV" "$RUN_DIR"

perfbench_print_summary "$RESULTS_TSV" "ASCYLIB HJ tree: glibc malloc vs jemalloc (paper Appendix B.2 / Table 4)" \
    "$SIFTER_ROOT/artifact/experiments/$OUT_NAME/summary.txt"
