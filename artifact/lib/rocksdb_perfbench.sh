#!/usr/bin/env bash
# Shared driver for the RocksDB *quantitative ablation* experiments: these
# reproduce Table 1's "RocksDB/prefix hash" and "RocksDB/inline skiplist"
# rows (paper Section 6.4) by building RocksDB's own (un-instrumented)
# db_bench binary in each of the paper's described configurations -- stock
# and with the fix applied -- and driving it with `perf stat`, mirroring
# the paper's own run_experiment_asplos.sh. Contrast with
# artifact/lib/rocksdb_experiment.sh, which runs the HeapLENS
# instrumentation/sampling/visualization pipeline on the stock HashSkipList
# memtable to produce a .sqlite database for the visualizer.
#
# Ported from rocksdb_exp/rocksdb/run_experiment_asplos.sh, trimmed to the
# two variants (per memtable) it actually exercises for each -- that
# script's own `for EXP_TYPE in 0 4` (rather than looping over its full,
# much longer `expNames` arrays) selects exactly the default and the
# paper's fix, out of several other exploratory configurations that were
# never the ones reported.
#
# Unlike ASCYLIB/TPC-C's ablations, these builds are NOT run through
# sifter.sh/clang-tidy at all -- no HeapLENS instrumentation, no memhook --
# so there's no equivalent to rocksdb_experiment.sh's file-ID-collision/
# malformed-insertion workarounds here. RocksDB's default DEBUG_LEVEL (1,
# i.e. NOT the DEBUG_LEVEL=0 the visualization experiment needs for a
# realistic runtime) is used as-is, so none of that experiment's -Werror/
# RTTI overrides are needed either. Building the `db_bench` target
# specifically (not the aggregate `benchmarks` target the reference script
# uses, which also builds 6 other tools this experiment never runs) keeps
# each rebuild faster.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/perfstat_common.sh"

# rocksdb_perfbench_setup <out_name>
# Fresh copy of vendored RocksDB. Sets the global ROCKSDB_SRC_COPY for use
# by the other functions in this file.
rocksdb_perfbench_setup() {
    local out_name="$1"
    ROCKSDB_PERFBENCH_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
    local ROCKSDB_SRC="$ROCKSDB_PERFBENCH_ROOT/artifact/vendor/rocksdb"
    local WORK="$ROCKSDB_PERFBENCH_ROOT/artifact/experiments/${out_name}/work"
    ROCKSDB_PERFBENCH_WORK="$WORK"
    ROCKSDB_SRC_COPY="$WORK/src"
    rm -rf "$WORK"
    mkdir -p "$WORK"
    cp -r "$ROCKSDB_SRC" "$ROCKSDB_SRC_COPY"
    # Same two fixups as rocksdb_experiment.sh step 1 -- see its comments
    # for why: a Windows checkout CRLF-corrupts RocksDB's own build shell
    # scripts, and the copied submodule gitlink is dangling once moved out
    # of its original location.
    find "$ROCKSDB_SRC_COPY/build_tools" -type f -print0 2>/dev/null | xargs -0 -r dos2unix -q
    rm -f "$ROCKSDB_SRC_COPY/.git"
}

# rocksdb_perfbench_build [make_args...]
rocksdb_perfbench_build() {
    (
        cd "$ROCKSDB_SRC_COPY"
        make clean > /tmp/rocksdb_perfbench_build.log 2>&1 || true
        make "$@" db_bench -j"${BUILD_JOBS}" >> /tmp/rocksdb_perfbench_build.log 2>&1 || {
            echo "    !!! build failed for args=[$*] -- see /tmp/rocksdb_perfbench_build.log" >&2
            tail -60 /tmp/rocksdb_perfbench_build.log >&2
            return 1
        }
    )
}

# rocksdb_perfbench_variant <results_tsv> <run_dir> <variant_label> \
#     <threads> <reps> <extra_db_bench_args...>
#
# Runs the already-built db_bench <reps> times under perf stat, recording
# throughput (db_bench's own "<n> ops/sec" figure) and hardware-counter
# rates. <extra_db_bench_args...> carries whatever's specific to the
# memtable under test (--memtablerep, --use_plain_table, --key_size, etc.)
# so this function stays memtable-agnostic.
rocksdb_perfbench_variant() {
    local results_tsv="$1" run_dir="$2" variant="$3" threads="$4" reps="$5"
    shift 5
    local extra_args=("$@")
    local jemalloc_lib="$ROCKSDB_PERFBENCH_ROOT/artifact/vendor/setbench/lib/libjemalloc.so"

    echo "  variant: $variant (threads=$threads)"
    for run_idx in $(seq 0 $((reps - 1))); do
        (
            cd "$ROCKSDB_SRC_COPY"
            rm -rf /tmp/rocksdb_perfbench_db
            export LD_PRELOAD="$jemalloc_lib"
            perfbench_run_rep "$results_tsv" "$run_dir" "$variant" "$threads" "$run_idx" \
                '(?<=micros/op )[0-9]+' 1 -- \
                numactl -i 0 taskset -c "0-$((threads - 1))" \
                ./db_bench \
                    --use_existing_db=0 \
                    --db=/tmp/rocksdb_perfbench_db \
                    "${extra_args[@]}" \
                    --threads="$threads"
        )
    done
}
