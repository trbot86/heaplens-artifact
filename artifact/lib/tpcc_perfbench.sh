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

# tpcc_perfbench_cap_threads <requested_threads>
# Prints the thread count to actually use. THREAD_CNT is compiled in and
# drives -pin's range 1:1 (see tpcc_perfbench_build/tpcc_perfbench_variant),
# so asking for more threads than the machine has real CPUs doesn't degrade
# gracefully -- it's been observed to abort (setbench's own "could not bind
# thread N to cpuset" path) or even segfault under contention. Cap to
# nproc and warn, rather than let the paper-scale default (24) silently
# fail on smaller dev machines.
tpcc_perfbench_cap_threads() {
    local requested="$1" ncpu
    ncpu="$(nproc)"
    if [ "$requested" -gt "$ncpu" ]; then
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
    rm -rf "$TPCC_PERFBENCH_WORK"
    mkdir -p "$TPCC_PERFBENCH_WORK"
    cp -r "$SIFTER_ROOT/artifact/vendor/setbench" "$TPCC_SRC_COPY"
    cp -r "$SIFTER_ROOT/artifact/patches/setbench-tpcc/." "$TPCC_SRC_COPY/"
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
            > /tmp/tpcc_perfbench_build.log 2>&1
        make -j THREAD_CNT="$threads" workload=TPCC data_structure_name="$ds_name" data_structure_opts="$opts" \
            >> /tmp/tpcc_perfbench_build.log 2>&1 || {
            echo "    !!! build failed for $ds_name threads=$threads opts=$opts -- see /tmp/tpcc_perfbench_build.log" >&2
            tail -60 /tmp/tpcc_perfbench_build.log >&2
            return 1
        }
    )
}

# tpcc_perfbench_variant <results_tsv> <run_dir> <variant_label> <ds_name> \
#     <threads> <reps> [preload_lib]
#
# Runs the already-built binary <reps> times under perf stat, recording
# throughput (setbench's own `throughput=` field, txns/sec) and
# hardware-counter rates.
tpcc_perfbench_variant() {
    local results_tsv="$1" run_dir="$2" variant="$3" ds_name="$4"
    local threads="$5" reps="$6" preload="${7:-}"

    echo "  variant: $variant (threads=$threads)"
    for run_idx in $(seq 0 $((reps - 1))); do
        (
            cd "$TPCC_MACROBENCH"
            [ -n "$preload" ] && export LD_PRELOAD="$preload"
            # See artifact/patches/setbench-tpcc/common/recordmgr/
            # allocator_new.h: -DMEMHOOK_SEG_DS variants dlopen a second
            # copy of an allocator library per database table, which
            # exhausts glibc's small default static-TLS surplus on modern
            # jemalloc/mimalloc builds. This is harmless to set even for
            # variants that don't use MEMHOOK_SEG_DS.
            export GLIBC_TUNABLES="glibc.rtld.optional_static_tls=4194304"
            perfbench_run_rep "$results_tsv" "$run_dir" "$variant" "$threads" "$run_idx" \
                '(?<=throughput=)[0-9.]+' 1 -- \
                numactl -i 0 "./bin/rundb_TPCC_${ds_name}" -pin "0-$((threads - 1))"
        )
    done
}
