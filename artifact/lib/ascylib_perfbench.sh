#!/usr/bin/env bash
# Shared driver for the ASCYLIB *quantitative ablation* experiments: these
# reproduce Table 1 rows 1-3 (EFRB/DVY/HJ trees) and Table 3/4's per-variant
# throughput and hardware-counter numbers by building ASCYLIB's own
# benchmark binaries (no HeapLENS instrumentation) and driving them with
# `perf stat`, exactly as the paper's run_experiment_asplos.sh did. Contrast
# with artifact/lib/ascylib_experiment.sh, which runs the HeapLENS
# instrumentation/sampling/visualization pipeline on the stock data
# structure to produce a .sqlite database for the visualizer.
#
# Ported from ASCYLIB's own run_experiment_asplos.sh (see git history / the
# HeapLENS paper's Section 6.2 and Appendix B for the source of each
# variant's parameters).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/perfstat_common.sh"
source "$SCRIPT_DIR/prepare_ascylib.sh"

# ascylib_perfbench_setup <out_name>
# Fresh copy of vendored ASCYLIB to build variants against. Sets the global
# ASCYLIB_SRC_COPY for use by the other functions in this file.
ascylib_perfbench_setup() {
    local out_name="$1"
    local SIFTER_ROOT
    SIFTER_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
    ASCYLIB_PERFBENCH_ROOT="$SIFTER_ROOT"
    ASCYLIB_PERFBENCH_WORK="$SIFTER_ROOT/artifact/experiments/${out_name}/work"
    ASCYLIB_SRC_COPY="$ASCYLIB_PERFBENCH_WORK/src"
    ASCYLIB_PERFBENCH_BUILD_LOG="$ASCYLIB_PERFBENCH_WORK/build.log"
    rm -rf "$ASCYLIB_PERFBENCH_WORK"
    mkdir -p "$ASCYLIB_PERFBENCH_WORK"
    cp -r "$SIFTER_ROOT/artifact/vendor/ascylib" "$ASCYLIB_SRC_COPY"
    prepare_ascylib "$SIFTER_ROOT" "$ASCYLIB_SRC_COPY"
}

# ascylib_perfbench_build <tree_src_dir> [make_args...]
# Builds directly from within <tree_src_dir> (each tree has its own local
# Makefile with a default `all` target -- ROOT=../.. pulls in
# common/Makefile.common for the flags below), matching the same pattern
# artifact/lib/ascylib_experiment.sh already uses successfully. make_args go
# straight onto the `make` command line, e.g. STM=LOCKFREE SET_CPU=0
# SEG_OBJS=1 INIT=all (see common/Makefile.common for what each flag does).
ascylib_perfbench_build() {
    local tree_src_dir="$1"
    shift
    (
        cd "$ASCYLIB_SRC_COPY/$tree_src_dir"
        # Ubuntu 22.04's gcc defaults to PIE; ASCYLIB's bundled ssmem static
        # lib predates that and isn't position-independent (see the same fix
        # in artifact/lib/ascylib_experiment.sh).
        export CFLAGS=-fno-pie LDFLAGS=-no-pie
        make clean "$@" > "$ASCYLIB_PERFBENCH_BUILD_LOG" 2>&1
        make "$@" >> "$ASCYLIB_PERFBENCH_BUILD_LOG" 2>&1 || {
            echo "    !!! build failed for $tree_src_dir $* -- see $ASCYLIB_PERFBENCH_BUILD_LOG" >&2
            tail -40 "$ASCYLIB_PERFBENCH_BUILD_LOG" >&2
            return 1
        }
    )
}

# ascylib_perfbench_variant <results_tsv> <run_dir> <variant_label> \
#     <binary_name> <threads> <initial> <range> <update_pct> <duration_ms> \
#     <reps> [preload_lib]
#
# Saves the already-built binary and registers its trials for the campaign.
# The campaign records throughput and hardware counters. [preload_lib] is
# empty by default: ASCYLIB's build already links its ssmem sub-allocator
# in statically (see common/Makefile.common's LDFLAGS), so no LD_PRELOAD is
# needed for the normal/glibc-malloc variants -- only pass one to swap in a
# different malloc implementation (e.g. jemalloc) for an allocator-swap
# variant.
ascylib_perfbench_variant() {
    local results_tsv="$1" run_dir="$2" variant="$3" binary_name="$4"
    local threads="$5" initial="$6" range="$7" update="$8" duration_ms="$9"
    local reps="${10}"
    local preload="${11:-}"
    local cpus="${PERFBENCH_CPUS:-0-$((threads - 1))}"
    local placement=(numactl "--physcpubind=$cpus" "--${PERFBENCH_MEMORY:-membind}=${PERFBENCH_NODE:-0}")
    if [[ "${ARTIFACT_NO_NUMA:-0}" == 1 ]]; then placement=(); fi
    sha256sum "$ASCYLIB_SRC_COPY/bin/$binary_name" | sed "s|$ASCYLIB_SRC_COPY/bin/$binary_name|$variant|" >> "${results_tsv}.binaries.sha256"

    echo "  save variant: $variant (threads=$threads initial=$initial update=$update%)"
    python3 "$PERFBENCH_CAMPAIGN_PY" add --plan "$run_dir/campaign.json" \
        --variant "$variant" --benchmark ascylib --threads "$threads" --reps "$reps" \
        --binary "$ASCYLIB_SRC_COPY/bin/$binary_name" --cwd "$ASCYLIB_SRC_COPY" \
        --preload "$preload" --library-path "$ASCYLIB_SRC_COPY/external/lib" \
        --build-log "$ASCYLIB_PERFBENCH_BUILD_LOG" -- \
        "${placement[@]}" "$ASCYLIB_SRC_COPY/bin/$binary_name" \
        -i "$initial" -r "$range" -n "$threads" -u "$update" -d "$duration_ms"
}
