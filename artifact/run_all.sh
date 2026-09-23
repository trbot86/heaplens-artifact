#!/usr/bin/env bash
# Runs every visualization (diagnostic-reproduction) experiment for the
# HeapLENS ATC'26 artifact -- not the performance experiments, see
# run_perfbench.sh for those. Each one takes roughly a few minutes, except
# the two TPC-C experiments and the RocksDB experiment, which additionally
# rebuild the instrumentation toolchain in C++/template mode -- RocksDB's
# own build is also the heaviest of the three targets (it compiles most of
# the RocksDB library to link db_bench). Unlike the other experiments, the
# TPC-C ones' own defaults (THREADS=2, RUN_SECONDS=10 -- see
# tpcc_experiment.sh) are NOT paper-matching even without --quick: TPC-C's
# role in this artifact is to demonstrate the instrumentation/sampling/
# visualization pipeline working end-to-end on the paper's actual case
# study, not to reproduce Table 1's throughput numbers, so a small,
# fast-to-populate warehouse count was chosen deliberately. Pass
# THREADS=24 (and optionally RUN_SECONDS=30) to each TPC-C run.sh directly
# if you want the paper's actual thread/warehouse count instead.
#
# Usage: artifact/run_all.sh [--quick]
#   --quick   shortens durations/workload sizes for a fast kick-the-tires pass
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "${1:-}" = "--quick" ]; then
    export DURATION_MS=1000
    export RUN_SECONDS=10
    export SAMPLE_PROPORTION=0.05
fi

"$SCRIPT_DIR/setup.sh"

EXPERIMENTS=(ascylib_efrb ascylib_dvy ascylib_hj tpcc_bcco tpcc_efrb rocksdb_hsl)
FAILED=()

for exp in "${EXPERIMENTS[@]}"; do
    echo
    echo "############################################################"
    echo "# $exp"
    echo "############################################################"
    if ! "$SCRIPT_DIR/experiments/$exp/run.sh"; then
        echo "!!! $exp FAILED" >&2
        FAILED+=("$exp")
    fi
done

echo
if [ "${#FAILED[@]}" -eq 0 ]; then
    echo "All experiments completed. Result databases are under artifact/experiments/*/*.sqlite"
else
    echo "The following experiments failed: ${FAILED[*]}" >&2
    exit 1
fi
