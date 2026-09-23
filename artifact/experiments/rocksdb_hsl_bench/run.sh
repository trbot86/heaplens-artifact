#!/usr/bin/env bash
# HeapLENS paper Section 6.4/Table 1: RocksDB's "prefix hash" memtable
# (HashSkipListRep), comparing stock allocation against the paper's fix for
# its 56B-per-bucket SkipList node (upstreamed as PR #13424 / commit
# 0c7e5bd): reordering two fields and dropping now-unnecessary padding to
# shrink it to 48B. This is the quantitative "before/after" ablation --
# contrast with artifact/experiments/rocksdb_hsl, which runs the HeapLENS
# instrumentation/sampling pipeline on the stock (pre-fix) memtable to
# produce a .sqlite database for the visualizer.
#
# Ported and cleaned up from rocksdb_exp/rocksdb/run_experiment_asplos.sh's
# --memtable-rep prefix_hash mode, trimmed to the two variants it actually
# exercises (`for EXP_TYPE in 0 4`, i.e. a_default and e_nopad out of six
# defined-but-unused exploratory configurations) and simplified to a single
# --disable_auto_compactions=true db_bench configuration instead of the
# reference script's separate 18-thread (explicit compaction throttling)
# and 36-thread (compaction disabled) cases, so THREADS isn't tied to a
# specific NUMA topology.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIFTER_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$SIFTER_ROOT/artifact/lib/rocksdb_perfbench.sh"

# Paper methodology (Section 6.4): readwhilewriting workload, 64B keys, 256B
# values, prefix hash memtable with a full-key prefix extractor. THREADS=18
# matches the smaller of the paper's two configurations (18/36, tied to its
# specific dual-socket hardware); override for your own machine.
THREADS="${THREADS:-18}"
REPS="${REPS:-3}"                    # paper used 10; override for full fidelity
EXPERIMENT="${EXPERIMENT:-readwhilewriting}"
NUM_KEYS="${NUM_KEYS:-10000000}"
KEY_SIZE="${KEY_SIZE:-64}"
VALUE_SIZE="${VALUE_SIZE:-256}"
DURATION_SECONDS="${DURATION_SECONDS:-10}"
BUILD_JOBS="${BUILD_JOBS:-4}"         # see rocksdb_experiment.sh: heavy -j can freeze Docker

OUT_NAME="rocksdb_hsl_bench"
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
    --use_plain_table=1
    --memtablerep=prefix_hash
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
rocksdb_perfbench_build
rocksdb_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "a_default" "$ACTUAL_THREADS" "$REPS" "${DB_BENCH_ARGS[@]}"

echo "=== [$OUT_NAME] b_nopad (reorder fields + drop padding, threads=$ACTUAL_THREADS) ==="
rocksdb_perfbench_build REORDER_FIELDS=1 NO_PADDING_NODE=1
rocksdb_perfbench_variant "$RESULTS_TSV" "$RUN_DIR" "b_nopad" "$ACTUAL_THREADS" "$REPS" "${DB_BENCH_ARGS[@]}"

perfbench_print_summary "$RESULTS_TSV" "RocksDB prefix hash memtable: default -> reorder+nopad fix (paper Section 6.4 / Table 1)" \
    "$SIFTER_ROOT/artifact/experiments/$OUT_NAME/summary.txt"
