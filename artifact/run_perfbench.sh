#!/usr/bin/env bash
# Runs the HeapLENS paper's quantitative "before/after" ablation experiments:
# these reproduce Table 1 (rows 1, 4, 5), Table 3, and Table 4 by building
# ASCYLIB's and setbench's own (un-instrumented) benchmark binaries and
# driving them with `perf stat`, exactly as the paper's own
# run_experiment_asplos*.sh scripts did. Each one prints a human-readable
# summary table (mean throughput + mean hardware-counter rates per variant)
# at the end, and writes the full per-run data to
# artifact/experiments/<name>/results.tsv.
#
# This is DIFFERENT from artifact/run_all.sh, which drives HeapLENS's own
# instrumentation/sampling/visualization pipeline (memhook + sifter.sh) to
# produce a .sqlite database per experiment for the web visualizer -- these
# scripts instead measure real performance deltas between the paper's
# "stock" and "fixed" configurations. See artifact/README.md's "Quantitative
# ablation experiments" section for the full list and paper cross-references.
#
# IMPORTANT: hardware-counter columns (cache-miss/TLB-miss/LLC-miss rates)
# require the host CPU's performance-monitoring unit (PMU) to be exposed to
# the container; this is NOT available under most Type-2 hypervisors
# (including Docker Desktop's WSL2/Hyper-V backend). See
# artifact/lib/perfstat_common.sh's header comment for details. Throughput
# numbers are unaffected and always meaningful.
#
# Usage: artifact/run_perfbench.sh [--quick]
#   --quick   uses small thread counts / node counts / a single repetition,
#             for a fast kick-the-tires pass instead of paper-scale numbers
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "${1:-}" = "--quick" ]; then
    export REPS=1
    export THREADS=4
    export DURATION_MS=1000
fi

"$SCRIPT_DIR/setup.sh"

EXPERIMENTS=(ascylib_efrb_bench ascylib_dvy_bench ascylib_hj_bench tpcc_bcco_bench tpcc_efrb_bench)
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
    echo "All ablation experiments completed. Per-run data: artifact/experiments/*/results.tsv"
    echo "Human-readable summaries: artifact/experiments/*/summary.txt"
else
    echo "The following experiments failed: ${FAILED[*]}" >&2
    exit 1
fi
