#!/usr/bin/env bash
# HeapLENS paper Section 6.4/Table 1: RocksDB's default "inline skiplist"
# memtable (the public InlineSkipList used by the default skip_list
# memtablerep -- a different data structure from rocksdb_hsl_bench's
# HashSkipListRep bucket SkipList, despite the similar name), comparing
# stock node layout against the paper's fix for tall (high-level) nodes
# spanning multiple cache lines: aligning tall nodes to the cache line size
# AND segregating them into their own memory region, together. This is the
# quantitative "before/after" ablation -- there is no corresponding
# HeapLENS instrumentation/visualization experiment for this memtable.
#
# Ported and cleaned up from rocksdb_exp/rocksdb/run_experiment_asplos.sh's
# --memtable-rep skip_list mode, trimmed to the two variants it actually
# exercises (`for EXP_TYPE in 0 4`, i.e. a_default and e_align_seg_tall out
# of ten defined-but-unused exploratory configurations) and simplified to a
# single --disable_auto_compactions=true db_bench configuration -- see
# rocksdb_hsl_bench/run.sh's header comment for why.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIFTER_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$SIFTER_ROOT/artifact/lib/rocksdb_perfbench.sh"

# Paper methodology (Section 6.4): readwhilewriting workload, 64B keys, 256B
# values. THREADS=18 matches the smaller of the paper's two configurations
# (18/36, tied to its specific dual-socket hardware); override for your own
# machine.
THREADS="${THREADS:-18}"
REPS="${REPS:-3}"                    # paper used 10; override for full fidelity
EXPERIMENT="${EXPERIMENT:-readwhilewriting}"
NUM_KEYS="${NUM_KEYS:-10000000}"
KEY_SIZE="${KEY_SIZE:-64}"
VALUE_SIZE="${VALUE_SIZE:-256}"
DURATION_SECONDS="${DURATION_SECONDS:-10}"
BUILD_JOBS="${BUILD_JOBS:-4}"         # see rocksdb_experiment.sh: heavy -j can freeze Docker
ALIGN_TALL_NODE="${ALIGN_TALL_NODE:-4}"
SEG_TALL_NODE="${SEG_TALL_NODE:-4}"

OUT_NAME="rocksdb_isl_bench"
RESULTS_TSV="$SIFTER_ROOT/artifact/experiments/$OUT_NAME/results.tsv"
RUN_DIR="$SIFTER_ROOT/artifact/experiments/$OUT_NAME/runs"

# readwhilewriting reserves one thread for the writer.
ACTUAL_THREADS="$THREADS"
[ "$EXPERIMENT" = "readwhilewriting" ] && ACTUAL_THREADS=$((THREADS - 1))

DB_BENCH_ARGS=(
    --benchmarks="filluniquerandom,$EXPERIMENT"
    --key_size="$KEY_SIZE"
    --prefix_size="$KEY_SIZE"
    --value_size="$VALUE_SIZE"
    --compression_type=none
    --use_plain_table=0
    --memtablerep=skip_list
    --max_write_buffer_number=2
    --write_buffer_size=134217728
    --disable_auto_compactions=true
    --bloom_bits=10
    --bloom_locality=1
    --num="$NUM_KEYS"
    --allow_concurrent_memtable_write=false
    --disable_wal=1
    --sync=0
    --duration="$DURATION_SECONDS"
)

echo "=== [$OUT_NAME] fresh working copy of RocksDB ==="
rocksdb_perfbench_setup "$OUT_NAME"
perfbench_init_results "$RESULTS_TSV"
rm -rf "$RUN_DIR"

echo "=== [$OUT_NAME] a_default (threads=$ACTUAL_THREADS) ==="
rocksdb_perfbench_build DISABLE_WARNING_AS_ERROR=1
rocksdb_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "a_default" "$ACTUAL_THREADS" "$REPS" "${DB_BENCH_ARGS[@]}"

echo "=== [$OUT_NAME] b_align_seg_tall (align + segregate tall nodes, threads=$ACTUAL_THREADS) ==="
rocksdb_perfbench_build DISABLE_WARNING_AS_ERROR=1 ALIGN_TALL_NODE="$ALIGN_TALL_NODE" SEG_TALL_NODE="$SEG_TALL_NODE"
rocksdb_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "b_align_seg_tall" "$ACTUAL_THREADS" "$REPS" "${DB_BENCH_ARGS[@]}"

perfbench_print_summary "$RESULTS_TSV" "RocksDB inline skiplist memtable: default -> align+segregate tall nodes fix (paper Section 6.4 / Table 1)" \
    "$SIFTER_ROOT/artifact/experiments/$OUT_NAME/summary.txt"
