#!/usr/bin/env bash
# HeapLENS paper Section 6.3 / Table 1 row 5: TPC-C benchmark (DBx1000/
# setbench) using the EFRB tree (Ellen et al.) as database index. Two
# separate anomalies are reproduced here, matching the paper's narrative:
#
#   1. a_jemalloc vs d_single_recmgr (both jemalloc + node segregation):
#      SetBench was found to spawn a separate EBR reclamation instance per
#      database table, leaving retired "block" objects accumulating rather
#      than being reclaimed. d_single_recmgr uses one shared instance for
#      all tables instead (-DMACROBENCH_SINGLE_RECMGR -DBST_ELLEN), which
#      the paper reports as a ~19% end-to-end improvement (text only, not a
#      Table 1 row).
#   2. b_mimalloc vs c_mimalloc_fixed (both mimalloc-backed, no single-
#      recmgr fix): swapping jemalloc for mimalloc revealed that mimalloc's
#      posix_memalign implementation wastes space aligning 48B row_t
#      objects to 64B (rounding up to 112B blocks); c_mimalloc_fixed
#      allocates 64B row_t objects instead (-DMACROBENCH_PAD_ROW_TO_ALIGN).
#      This is Table 1 row 5 (+20% throughput, -35% cache misses, -92% TLB
#      misses).
#
# Contrast with artifact/experiments/tpcc_efrb, which runs the HeapLENS
# instrumentation/sampling pipeline on the stock tree to produce a .sqlite
# database for the visualizer.
#
# Ported and cleaned up from setbench_exp's macrobench/
# run_experiment_asplos_ellen.sh, preserving its exact variant/flag
# combinations (including that c_mimalloc_fixed does NOT also pass
# -DMEMHOOK_SEG_DS, unlike a/b/d/e -- kept faithful to the original script
# since it's what the paper's published mimalloc numbers were measured
# with).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIFTER_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$SIFTER_ROOT/artifact/lib/tpcc_perfbench.sh"

THREADS="${THREADS:-24}"
REPS="${REPS:-3}"   # paper used 10; override for full fidelity

OUT_NAME="tpcc_efrb_bench"
RESULTS_TSV="$SIFTER_ROOT/artifact/experiments/$OUT_NAME/results.tsv"
RUN_DIR="$SIFTER_ROOT/artifact/experiments/$OUT_NAME/runs"
DS_NAME="ellen_ext_bst_lf"

echo "=== [$OUT_NAME] fresh working copy of setbench ==="
tpcc_perfbench_setup "$OUT_NAME"
perfbench_init_results "$RESULTS_TSV"
rm -rf "$RUN_DIR"
JEMALLOC_LIB="$TPCC_SRC_COPY/lib/libjemalloc.so"
MIMALLOC_LIB="$TPCC_SRC_COPY/lib/libmimalloc.so"

echo "=== [$OUT_NAME] a_jemalloc (threads=$THREADS) ==="
tpcc_perfbench_build "$DS_NAME" "$THREADS" "-DDEBRA_ORIGINAL_FREE -DMEMHOOK_SEG_DS"
tpcc_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "a_jemalloc" "$DS_NAME" "$THREADS" "$REPS" "$JEMALLOC_LIB"

echo "=== [$OUT_NAME] b_mimalloc (threads=$THREADS) ==="
tpcc_perfbench_build "$DS_NAME" "$THREADS" "-DDEBRA_ORIGINAL_FREE -DMEMHOOK_SEG_DS"
tpcc_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "b_mimalloc" "$DS_NAME" "$THREADS" "$REPS" "$MIMALLOC_LIB"

echo "=== [$OUT_NAME] c_mimalloc_fixed (threads=$THREADS) ==="
tpcc_perfbench_build "$DS_NAME" "$THREADS" "-DDEBRA_ORIGINAL_FREE -DMACROBENCH_PAD_ROW_TO_ALIGN"
tpcc_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "c_mimalloc_fixed" "$DS_NAME" "$THREADS" "$REPS" "$MIMALLOC_LIB"

echo "=== [$OUT_NAME] d_single_recmgr (threads=$THREADS) ==="
tpcc_perfbench_build "$DS_NAME" "$THREADS" "-DDEBRA_ORIGINAL_FREE -DMEMHOOK_SEG_DS -DMACROBENCH_SINGLE_RECMGR -DBST_ELLEN"
tpcc_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "d_single_recmgr" "$DS_NAME" "$THREADS" "$REPS" "$JEMALLOC_LIB"

echo "=== [$OUT_NAME] e_single_recmgr_mimalloc_fixed (threads=$THREADS) ==="
tpcc_perfbench_build "$DS_NAME" "$THREADS" "-DDEBRA_ORIGINAL_FREE -DMEMHOOK_SEG_DS -DMACROBENCH_PAD_ROW_TO_ALIGN -DMACROBENCH_SINGLE_RECMGR -DBST_ELLEN"
tpcc_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "e_single_recmgr_mimalloc_fixed" "$DS_NAME" "$THREADS" "$REPS" "$MIMALLOC_LIB"

perfbench_print_summary "$RESULTS_TSV" "TPC-C/EFRB tree: allocator swap + single-recmgr + row-padding ablations (paper Section 6.3 / Table 1 row 5)" \
    "$SIFTER_ROOT/artifact/experiments/$OUT_NAME/summary.txt"
