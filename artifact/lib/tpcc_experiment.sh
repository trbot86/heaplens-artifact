#!/usr/bin/env bash
# Shared driver for the TPC-C / setbench macrobench diagnostic experiments
# (HeapLENS paper Section 6.3, Table 1 rows 4-5: BCCO tree and EFRB tree used
# as the DBx1000-derived TPC-C database index).
#
# Diagnostic only -- see artifact/lib/ascylib_experiment.sh for the
# same caveat. This reproduces the sampled database behind e.g. Figure 9's
# huge-page density heatmap, not the claimed +16%/+20% throughput numbers
# (see the corresponding tpcc_bcco_bench/tpcc_efrb_bench experiments for
# those).
#
# Two things worth knowing before editing this script or the patches it
# applies (artifact/patches/setbench-tpcc/, overlaid in step 1 below):
#   - mem_alloc::alloc's template overload lives in patches/setbench-tpcc/
#     macrobench/system/mem_alloc.h, guarded on __MEMHOOK_INTERFACE_H (that
#     header's own include-guard macro). sifter.sh's --includes-only step
#     (step 4) prepends `#include "memhook_interface.h"` as the literal
#     first line of every file, so the guard is defined if and only if this
#     is an instrumented build -- the same patched file compiles unchanged
#     as a stock build too.
#   - The patches directory is a plain superproject directory, not changes
#     committed inside the setbench submodule: a submodule only tracks a
#     commit SHA, not working-tree state, so anything committed only there
#     would silently vanish on the next `git submodule update`. Its schema
#     data files are also CRLF-normalized (`text=lf` in .gitattributes),
#     since a Windows checkout otherwise corrupts them in a way that
#     crashes the benchmark at runtime (getline() doesn't strip \r, so a
#     parsed index name silently mismatches its lookup elsewhere). See
#     artifact/README.md's vendored-dependencies section for the rest of
#     what's in this directory and why.
#
# Usage: run_tpcc_experiment <data-structure-name> <out-name>
#   data-structure-name : setbench ds/ name, e.g. bronson_pext_bst_occ or ellen_ext_bst_lf
#   out-name             : short slug for this experiment's working directories

set -euo pipefail

run_tpcc_experiment() {
    local ds_name="$1"
    local out_name="$2"

    local SIFTER_ROOT
    SIFTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    local SETBENCH_SRC="$SIFTER_ROOT/artifact/vendor/setbench"
    local RUN_ROOT="${ARTIFACT_RUN_DIR:-$SIFTER_ROOT/artifact/experiments/${out_name}}"
    local WORK="$RUN_ROOT/work"
    local SRC_COPY="${WORK}/src"
    local INSTRUMENTED="${WORK}/instrumented"
    local MEMHOOK_DIR="$SIFTER_ROOT/memhook"
    local MB_SUBDIR="macrobench"

    # Paper Section 6.3: TPC-C OLTP workload via db_bench-equivalent
    # (setbench's own rundb_TPCC_* harness). THREAD_CNT is compiled in (see
    # step 5 below); NUM_WH tracks it 1:1 (warehouses = threads, the
    # standard low-contention TPC-C config, via config.h), matching the
    # paper's reference run scripts, which only ever pass -pin and never
    # override warehouse count separately.
    #
    # The paper figure recipe has 24 workers/warehouses; ae.py selects two
    # for --profile smoke. These are diagnostic traces, not timing results.
    local THREADS="${THREADS:-24}"
    local RUN_SECONDS="${RUN_SECONDS:-10}"

    local SAMPLE_PROPORTION="${SAMPLE_PROPORTION:-0.2}"
    local PAGES_PER_TYPE="${PAGES_PER_TYPE:-1}"

    echo "=== [$out_name] 1/7: fresh working copy of setbench (with submodules) ==="
    [[ ! -e "$WORK" ]] || { echo "Refusing to overwrite $WORK" >&2; return 1; }
    mkdir -p "$WORK"
    cp -r "$SETBENCH_SRC" "$SRC_COPY"
    if [ ! -e "$SRC_COPY/common/recordmgr/allocator_bump.h" ]; then
        echo "ERROR: common/recordmgr submodule not initialized in artifact/vendor/setbench." >&2
        echo "Run: git -C artifact/vendor/setbench submodule update --init common/recordmgr tools" >&2
        exit 1
    fi
    mkdir -p "$SRC_COPY/$MB_SUBDIR/bin"
    # Overlay artifact/patches/setbench-tpcc/ on top of the freshly-copied
    # vendor source -- see the file-header comment above for why this lives
    # in the superproject rather than committed inside the submodule.
    cp -r "$SIFTER_ROOT/artifact/patches/setbench-tpcc/." "$SRC_COPY/"
    source "$SIFTER_ROOT/artifact/lib/tpcc_allocators.sh"
    tpcc_stage_allocators "$SIFTER_ROOT" "$SRC_COPY"
    if [[ "$out_name" == tpcc_hj ]]; then
        python3 "$SIFTER_ROOT/artifact/lib/hj_figure.py" "$SRC_COPY"
    fi
    local trace_opts="" trace_allocator="libjemalloc.so"
    case "$out_name:${TRACE_VARIANT:-baseline}" in
        tpcc_hj:baseline) ;;
        tpcc_bcco:baseline) ;;
        tpcc_bcco:segregation-only) trace_opts="-DMEMHOOK_SEG_DS" ;;
        tpcc_bcco:optimized) trace_opts="-DMEMHOOK_SEG_DS -DMACROBENCH_PACK_LOCK" ;;
        tpcc_efrb:baseline) trace_opts="-DDEBRA_ORIGINAL_FREE -DMEMHOOK_SEG_DS"; trace_allocator="libmimalloc.so" ;;
        tpcc_efrb:optimized) trace_opts="-DDEBRA_ORIGINAL_FREE -DMEMHOOK_SEG_DS -DMACROBENCH_PAD_ROW_TO_ALIGN -DMACROBENCH_SINGLE_RECMGR -DBST_ELLEN"; trace_allocator="libmimalloc.so" ;;
        *) echo "Unsupported trace variant" >&2; return 2 ;;
    esac
    if [[ "${HEAPLENS_BCCO_FIGURE:-0}" == 1 ]]; then
        # Distinct files ensure distinct jemalloc instances. Never symlink them.
        cp "$SRC_COPY/lib/libjemalloc-heaplens.so" "$SRC_COPY/lib/global-jemalloc53.so"
        trace_allocator="global-jemalloc53.so"
        # Fail before instrumenting the full application if backing cannot be audited.
        g++ -std=c++17 -O2 "$SIFTER_ROOT/artifact/lib/bcco_figure_preflight.cpp" -ldl -o "$WORK/figure-preflight"
        timeout 30 env GLIBC_TUNABLES=glibc.rtld.optional_static_tls=4194304 \
            MALLOC_CONF=thp:always,metadata_thp:disabled HL_FIG9_THP=on \
            HL_FIG9_GLOBAL="$SRC_COPY/lib/$trace_allocator" \
            HL_FIG9_NODE="$SRC_COPY/lib/libjemalloc-heaplens.so" \
            "$WORK/figure-preflight" > "$RUN_ROOT/figure-preflight.log" 2>&1 || {
                cat "$RUN_ROOT/figure-preflight.log" >&2
                echo "BCCO figure needs two independent jemalloc 5.3 instances and permitted Linux 6.8+ PAGEMAP_SCAN/MADV_COLLAPSE." >&2
                return 1
            }
    fi

    echo "=== [$out_name] 2/7: build instrumentation toolchain + generate fixes.yaml ==="
    # setbench's macrobench is C++ (-std=c++17) -- use -t/--template so type
    # information is inferred via typeid (see README "Step 1"). sifter.sh's
    # own internal memhook build (triggered by this call) uses plain `make
    # -j` with no `clean` first, so if memhook was last built for a
    # *different* experiment (e.g. ASCYLIB, with -DMEMHOOK_ASCYLIB and
    # without -DUSE_TEMPLATE), Make's timestamp-based tracking has no way to
    # know the flags changed and silently reuses the stale .so -- force a
    # clean here so this run gets memhook built the way *it* needs.
    (cd "$MEMHOOK_DIR" && make clean) || true
    cd "$SIFTER_ROOT"
    ./sifter.sh "$SRC_COPY" "$INSTRUMENTED" \
        -t \
        -s "$MB_SUBDIR" \
        --skip-refactor \
        --build "bear -- make -j${JOBS:-4} THREAD_CNT=${THREADS} workload=TPCC data_structure_name=${ds_name} data_structure_opts='${trace_opts}'"

    echo "=== [$out_name] 3/7: apply clang-tidy fixes ==="
    (cd "$INSTRUMENTED" && clang-apply-replacements-14 ./)

    echo "=== [$out_name] 4/7: add memhook_interface.h includes ==="
    ./sifter.sh "$INSTRUMENTED" --includes-only
    # The record-manager header and dlsym allocator need explicit typed hooks.
    # Keep this file ID disjoint from the IDs assigned by source rewriting.
    if grep -q '^65004|' "$INSTRUMENTED/$MB_SUBDIR/fileset_dump.txt"; then
        echo "ERROR: TPC-C record-manager file ID already in use" >&2
        return 1
    fi
    printf '65004|%s\n' "$INSTRUMENTED/common/recordmgr/allocator_new.h" >> "$INSTRUMENTED/$MB_SUBDIR/fileset_dump.txt"
    if [[ "${HEAPLENS_BCCO_FIGURE:-0}" == 1 ]]; then
        python3 "$SIFTER_ROOT/artifact/lib/bcco_figure.py" "$INSTRUMENTED/$MB_SUBDIR" "${TRACE_VARIANT:-baseline}"
    fi
    # No separate mem_alloc::alloc patch step here -- it's already baked
    # into patches/setbench-tpcc/macrobench/system/mem_alloc.h (see the
    # file-header comment above) and was applied back in step 1.

    echo "=== [$out_name] 5/7: rebuild target linked against memhook ==="
    (
        cd "$INSTRUMENTED/$MB_SUBDIR"
        make clean workload=TPCC data_structure_name="$ds_name" || true
        # setbench's macrobench/Makefile does a plain `CFLAGS =`/`LDFLAGS =`
        # reset before its own `+=` lines, so neither a `make CFLAGS=...`
        # command-line arg (frozen by Make) nor a CFLAGS *environment*
        # variable (wiped out by that reset) survives to the actual
        # compile/link -- use the Makefile's own extension hook instead
        # (`CFLAGS += $(xargs)`, line 16). -DTHREAD_CNT=$THREADS is folded
        # in here too: it's a compile-time constant sizing several fixed
        # per-thread arrays (config.h's default is 8), not just the
        # runtime -tINT override parser.cpp also accepts.
        make -j"${JOBS:-4}" THREAD_CNT="$THREADS" workload=TPCC data_structure_name="$ds_name" data_structure_opts="$trace_opts" \
            xargs="-DHEAPLENS_TPCC_TRACE=1 -DTHREAD_CNT=${THREADS} -I${MEMHOOK_DIR} -L${MEMHOOK_DIR} -Wl,-rpath=${MEMHOOK_DIR} -lmemhook -ldl"
    )

    echo "=== [$out_name] 6/7: run instrumented TPC-C benchmark ==="
    echo "    threads=$THREADS warehouses=$THREADS (NUM_WH tracks THREAD_CNT, see patches/setbench-tpcc/macrobench/config.h)"
    (
        cd "$INSTRUMENTED/$MB_SUBDIR"
        # -pin takes a literal core-range string (system/thread_pinning.h),
        # e.g. "0-23" for 24 threads -- NOT "-t"/"-n" as separate argv
        # tokens (those silently zero g_thread_cnt instead). The +300s
        # grace margin (well beyond RUN_SECONDS, the workload's own timed
        # phase) is deliberate: memhook logs every allocation, and
        # warehouse/table population alone is measurably slower under
        # instrumentation than stock, before the timed phase even starts.
        local placement=() runtime_env=("GLIBC_TUNABLES=glibc.rtld.optional_static_tls=4194304") pin="${TRACE_CPUS:-0-$((THREADS - 1))}" bound="$((RUN_SECONDS + 300))"
        if [[ -n "${TRACE_CPUS:-}" ]]; then
            placement=(numactl "--physcpubind=$TRACE_CPUS" "--${TRACE_MEMORY:-membind}=${TRACE_NODE:-0}")
        fi
        if [[ "${HEAPLENS_BCCO_FIGURE:-0}" == 1 ]]; then
            mkdir "$RUN_ROOT/backing"
            runtime_env=("GLIBC_TUNABLES=glibc.rtld.optional_static_tls=4194304"
                "MALLOC_CONF=thp:always,metadata_thp:disabled" "HL_FIG9_THP=on"
                "HL_FIG9_GLOBAL=$INSTRUMENTED/lib/$trace_allocator"
                "HL_FIG9_NODE=$INSTRUMENTED/lib/libjemalloc-heaplens.so" "HL_FIG9_EVIDENCE=$RUN_ROOT/backing")
            bound=1200
        fi
        timeout "$bound" "${placement[@]}" env "${runtime_env[@]}" LD_PRELOAD="$MEMHOOK_DIR/libmemhook.so:$INSTRUMENTED/lib/$trace_allocator" \
            "./bin/rundb_TPCC_${ds_name}" -pin "$pin" |& tee "$RUN_ROOT/benchmark.log"
    )
    # Expected outputs in $INSTRUMENTED/$MB_SUBDIR: binary_dump.txt,
    # fileset_dump.txt, typeset_dump.txt, fielddump.txt

    echo "=== [$out_name] 7/7: sample into sqlite database ==="
    cd "$SIFTER_ROOT"
    local seed_args=() page_size=2097152
    [[ "$out_name" != tpcc_hj ]] || page_size=4096
    [[ -z "${SAMPLE_SEED:-}" ]] || seed_args=(--seed "$SAMPLE_SEED")
    ./sifter.sh "$INSTRUMENTED" -d -s "$MB_SUBDIR" \
        "${seed_args[@]}" \
        --num-buckets 2000 \
        --sample "$SAMPLE_PROPORTION" \
        --pages-per-type "$PAGES_PER_TYPE" \
        --field-dump fielddump.txt \
        --page-size "$page_size"

    local RESULT_DB="$RUN_ROOT/${out_name}.sqlite"
    cp "$SIFTER_ROOT/type_analysis/allocs.sqlite" "$RESULT_DB"
    python3 "$SIFTER_ROOT/artifact/check_database.py" "$RESULT_DB"
    if [[ "$out_name" == tpcc_bcco ]]; then
        python3 "$SIFTER_ROOT/artifact/check_tpcc_nodes.py" "$RESULT_DB" \
            --output "$RUN_ROOT/node-coverage.json"
    fi
    echo "=== [$out_name] done. Database: $RESULT_DB ==="
    echo "    Open it in the visualizer in huge-page mode to inspect segregation of"
    echo "    data-structure nodes vs. database rows (cf. paper Figure 9)."
}
