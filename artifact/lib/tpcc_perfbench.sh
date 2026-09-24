#!/usr/bin/env bash
# Shared driver for the setbench/TPC-C *quantitative ablation* experiments:
# these reproduce Table 1 rows 4-5 (TPC-C/BCCO and TPC-C/EFRB trees) by
# building setbench's own macrobench binaries (no HeapLENS instrumentation)
# and driving them with `perf stat`, exactly as the paper's
# run_experiment_asplos_{bronson,ellen}.sh did. Contrast with
# artifact/lib/tpcc_experiment.sh, which runs the HeapLENS instrumentation/
# sampling/visualization pipeline on the stock data structure to produce a
# .sqlite database for the visualizer.
#
# Ported from setbench's macrobench/run_experiment_asplos_bronson.sh and
# run_experiment_asplos_ellen.sh (see the HeapLENS paper's Section 6.3 for
# the source of each variant's parameters).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/perfstat_common.sh"
source "$SCRIPT_DIR/tpcc_allocators.sh"

# tpcc_perfbench_cap_threads <requested_threads>
# Prints the thread count to actually use. THREAD_CNT is compiled in and
# drives -pin's range 1:1 (see tpcc_perfbench_build/tpcc_perfbench_variant),
# so asking for more threads than the machine has real CPUs doesn't degrade
# gracefully -- it's been observed to abort (setbench's own "could not bind
# thread N to cpuset" path) or even segfault under contention. Cap to
# the available CPU affinity and warn, rather than let the paper-scale default (24) silently
# fail on smaller dev machines.
tpcc_perfbench_cap_threads() {
    local requested="$1" ncpu
    # OpenMP limits affect nproc, but not this pthread-based benchmark.
    ncpu="$(python3 -c 'import os; print(len(os.sched_getaffinity(0)))')"
    if [ "$requested" -gt "$ncpu" ]; then
        if [[ "${ARTIFACT_PROFILE:-smoke}" == paper ]]; then
            echo "Paper profile requires $requested CPUs; only $ncpu available. Use smoke on this host." >&2
            return 1
        fi
        echo "WARNING: THREADS=$requested exceeds this machine's $ncpu CPUs;" >&2
        echo "         TPC-C's macrobench binaries don't degrade gracefully" >&2
        echo "         when oversubscribed this way. Capping to $ncpu." >&2
        echo "$ncpu"
    else
        echo "$requested"
    fi
}

# tpcc_perfbench_setup <out_name>
# Fresh copy of vendored setbench, overlaid with artifact/patches/
# setbench-tpcc (the same fixed schema files, macrobench source fixes, and
# now also common/recordmgr/allocator_new.h's -DMEMHOOK_SEG_DS support --
# see that file for why it's needed) used by artifact/lib/tpcc_experiment.sh.
# Sets the global TPCC_SRC_COPY / TPCC_MACROBENCH for use by the other
# functions in this file.
tpcc_perfbench_setup() {
    local out_name="$1"
    local SIFTER_ROOT
    SIFTER_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
    TPCC_PERFBENCH_ROOT="$SIFTER_ROOT"
    TPCC_PERFBENCH_WORK="$SIFTER_ROOT/artifact/experiments/${out_name}/work"
    TPCC_SRC_COPY="$TPCC_PERFBENCH_WORK/src"
    TPCC_MACROBENCH="$TPCC_SRC_COPY/macrobench"
    TPCC_PERFBENCH_BUILD_LOG="$TPCC_PERFBENCH_WORK/build.log"
    rm -rf "$TPCC_PERFBENCH_WORK"
    mkdir -p "$TPCC_PERFBENCH_WORK"
    cp -r "$SIFTER_ROOT/artifact/vendor/setbench" "$TPCC_SRC_COPY"
    cp -r "$SIFTER_ROOT/artifact/patches/setbench-tpcc/." "$TPCC_SRC_COPY/"
    tpcc_stage_allocators "$SIFTER_ROOT" "$TPCC_SRC_COPY"
}

# tpcc_perfbench_build <ds_name> <threads> [data_structure_opts]
# Mirrors compile.sh's make_workload_dict(): a `make clean` pass, then a
# real build with THREAD_CNT baked in at compile time (NUM_WH and various
# array sizes in config.h derive from THREAD_CNT -- see
# artifact/patches/setbench-tpcc/macrobench/config.h).
tpcc_perfbench_build() {
    local ds_name="$1" threads="$2" opts="${3:-}"
    (
        cd "$TPCC_MACROBENCH"
        make clean workload=TPCC data_structure_name="$ds_name" data_structure_opts="$opts" \
            > "$TPCC_PERFBENCH_BUILD_LOG" 2>&1
        make -j"${JOBS:-4}" THREAD_CNT="$threads" workload=TPCC data_structure_name="$ds_name" data_structure_opts="$opts" \
            >> "$TPCC_PERFBENCH_BUILD_LOG" 2>&1 || {
            echo "    !!! build failed for $ds_name threads=$threads opts=$opts -- see $TPCC_PERFBENCH_BUILD_LOG" >&2
            tail -60 "$TPCC_PERFBENCH_BUILD_LOG" >&2
            return 1
        }
    )
}

# tpcc_perfbench_variant <results_tsv> <run_dir> <variant_label> <ds_name> \
#     <threads> <reps> [preload_lib]
#
# Saves the already-built binary and registers its trials for the campaign.
# The campaign records throughput (txns/sec) and hardware counters.
tpcc_perfbench_variant() {
    local results_tsv="$1" run_dir="$2" variant="$3" ds_name="$4"
    local threads="$5" reps="$6" preload="${7:-}"
    local cpus="${PERFBENCH_CPUS:-0-$((threads - 1))}"
    local placement=(numactl "--physcpubind=$cpus" "--${PERFBENCH_MEMORY:-membind}=${PERFBENCH_NODE:-0}")
    # SetBench accepts ranges and period-separated lists, not comma-separated lists.
    local pin=(-pin "${cpus//,/.}")
    if [[ "${ARTIFACT_NO_NUMA:-0}" == 1 ]]; then placement=(); pin=(); fi

    echo "  save variant: $variant (threads=$threads)"
    python3 "$PERFBENCH_CAMPAIGN_PY" add --plan "$run_dir/campaign.json" \
        --variant "$variant" --benchmark tpcc --threads "$threads" --reps "$reps" \
        --binary "$TPCC_MACROBENCH/bin/rundb_TPCC_${ds_name}" --cwd "$TPCC_MACROBENCH" \
        --preload "$preload" --build-log "$TPCC_PERFBENCH_BUILD_LOG" -- \
        "${placement[@]}" "$TPCC_MACROBENCH/bin/rundb_TPCC_${ds_name}" "${pin[@]}"
}
