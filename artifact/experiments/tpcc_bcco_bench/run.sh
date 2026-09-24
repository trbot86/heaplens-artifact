#!/usr/bin/env bash
# HeapLENS paper Section 6.3 / Table 1 row 4: TPC-C benchmark (DBx1000/
# setbench) using the BCCO tree (Bronson et al.) as database index,
# comparing stock allocation against the paper's two fixes: (1) segregating
# tree nodes into their own memory arena so they're densely packed onto
# huge pages instead of interleaved with the rest of DBx1000's allocations,
# and (2) replacing each row lock's `pthread_mutex_t*` indirection with a
# packed 4-byte spinlock. This is the quantitative "before/after" ablation
# -- contrast with artifact/experiments/tpcc_bcco, which runs the HeapLENS
# instrumentation/sampling pipeline on the stock tree to produce a .sqlite
# database for the visualizer.
#
# Ported and cleaned up from setbench_exp's macrobench/
# run_experiment_asplos_bronson.sh, trimmed to the variants the paper
# actually reports (a_bronson_default -> b_bronson_seg_ds -> c_bronson_
# pack_lock, matching the paper's own "+5% from segregation, cumulatively
# -22%/-43%/+16% with the row-lock fix too" narrative). The reference
# script's 4th variant (d_bronson_single_recmgr) is dropped here: the paper
# only describes the single-recmgr/EBR fix in the context of the EFRB tree
# (see tpcc_efrb_bench), not BCCO.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIFTER_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$SIFTER_ROOT/artifact/lib/tpcc_perfbench.sh"

THREADS="$(tpcc_perfbench_cap_threads "${THREADS:-24}")"
REPS="${REPS:-3}"   # paper used 10; override for full fidelity

OUT_NAME="tpcc_bcco_bench"
RESULTS_TSV="$SIFTER_ROOT/artifact/experiments/$OUT_NAME/results.tsv"
RUN_DIR="$SIFTER_ROOT/artifact/experiments/$OUT_NAME/runs"
DS_NAME="bronson_pext_bst_occ"

echo "=== [$OUT_NAME] fresh working copy of setbench ==="
tpcc_perfbench_setup "$OUT_NAME"
perfbench_init_results "$RESULTS_TSV"
rm -rf "$RUN_DIR"
JEMALLOC_LIB="$TPCC_SRC_COPY/lib/libjemalloc.so"

echo "=== [$OUT_NAME] a_bronson_default (threads=$THREADS) ==="
tpcc_perfbench_build "$DS_NAME" "$THREADS" ""
tpcc_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "a_default" "$DS_NAME" "$THREADS" "$REPS" "$JEMALLOC_LIB"

echo "=== [$OUT_NAME] b_bronson_seg_ds (threads=$THREADS) ==="
tpcc_perfbench_build "$DS_NAME" "$THREADS" "-DMEMHOOK_SEG_DS"
tpcc_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "b_seg_ds" "$DS_NAME" "$THREADS" "$REPS" "$JEMALLOC_LIB"

echo "=== [$OUT_NAME] c_bronson_pack_lock (threads=$THREADS) ==="
tpcc_perfbench_build "$DS_NAME" "$THREADS" "-DMEMHOOK_SEG_DS -DMACROBENCH_PACK_LOCK"
tpcc_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "c_seg_ds_pack_lock" "$DS_NAME" "$THREADS" "$REPS" "$JEMALLOC_LIB"

perfbench_run_campaign "$RESULTS_TSV" "$RUN_DIR"

perfbench_print_summary "$RESULTS_TSV" "TPC-C/BCCO tree: default -> node segregation -> +row-lock fix (paper Section 6.3 / Table 1 row 4)" \
    "$SIFTER_ROOT/artifact/experiments/$OUT_NAME/summary.txt"
