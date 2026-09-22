#!/usr/bin/env bash
# Shared driver for the TPC-C / setbench macrobench diagnostic experiments
# (HeapLENS paper Section 6.3, Table 1 rows 4-5: BCCO tree and EFRB tree used
# as the DBx1000-derived TPC-C database index).
#
# SCOPE: diagnostic only -- see artifact/lib/ascylib_experiment.sh for the
# same caveat. This reproduces the sampled database behind e.g. Figure 6's
# huge-page density heatmap, not the claimed +16%/+20% throughput numbers
# (which require re-implementing the paper's index-segregation fix).
#
# STATUS (2026-09-22, verified end-to-end in docker/ubuntu_22_04): BOTH
# TPC-C data structures (ellen_ext_bst_lf / tpcc_efrb, bronson_pext_bst_occ
# / tpcc_bcco) build, instrument, and run to full completion -- all 7 steps,
# producing real, substantial .sqlite databases (tested at THREADS=2: ~328MB
# / 4.67M sampled rows for ellen, ~255MB / 3.88M rows for bronson) with
# exactly the types the paper describes analyzing: node_t<...> (the actual
# EFRB/BCCO tree node type), row_t/Row_lock/LockEntry/pthread_mutex_t (the
# TPC-C row/lock structures from Fig. 6-7), and block/blockpool/blockbag
# (SetBench's EBR reclamation internals, matching the "unexpected buildup
# of block objects" anomaly described in paper Sec. 6.3). This was
# previously blocked by a SIGSEGV; the fix required several real, distinct
# bugs found and fixed, documented here in the order that matters for
# understanding the pipeline, not the (much messier) order they were found:
#
# 1. mem_alloc::alloc's template overload now lives in patches/setbench-
#    tpcc/macrobench/system/mem_alloc.h (baked into the class body, guarded
#    on __MEMHOOK_INTERFACE_H) instead of being patched in at runtime here.
#    AllocationLoggingCheck's MATCH_FUNCTIONS list targets "alloc" by bare
#    name, so `mem_allocator.alloc(size, part_id)` call sites get rewritten
#    to `mem_allocator.alloc<Type, __LINE__, fileID>(...)`, which needs a
#    matching template overload to compile; it delegates straight to
#    memhook_interface.h's own malloc<T,line,filename> template rather than
#    duplicating its logging logic. Guarding on __MEMHOOK_INTERFACE_H
#    (memhook_interface.h's own include-guard macro, not an ad hoc flag)
#    works because sifter.sh's --includes-only step prepends `#include
#    "memhook_interface.h"` as the literal first line of every file
#    (including this one) -- so by the time this class body is parsed,
#    __MEMHOOK_INTERFACE_H is defined if and only if this is an
#    instrumented build, and the SAME patched file compiles unaffected as a
#    stock (non-instrumented) build (the template simply isn't there to
#    call malloc<T,line,filename>, which itself wouldn't be declared
#    either).
#
# 2. The actual SIGSEGV: schema data files under macrobench/benchmarks/
#    (TPCC_full_schema.txt et al) got CRLF-corrupted by a Windows checkout
#    of this repo's setbench submodule (core.autocrlf=true) -- the same
#    corruption class documented elsewhere in this repo for llvm.sh and
#    RocksDB's build_tools scripts, except this time in a .txt *data* file
#    that no .gitattributes rule (which only covers scripts) protects.
#    workload::init_schema() reads index names out of this file with plain
#    getline(), which doesn't strip \r, so an index declared as
#    "Index=CUSTOMER_ID_IDX\r\n" gets registered in the `indexes` map under
#    the key "CUSTOMER_ID_IDX\r", not "CUSTOMER_ID_IDX". Elsewhere (e.g.
#    tpcc_wl.cpp's `i_customer_id = indexes["CUSTOMER_ID_IDX"]`), the code
#    looks the same index up by its clean literal name; since
#    std::map::operator[] silently inserts a new null-valued entry for a
#    key that doesn't exist, that lookup doesn't fail -- it creates a
#    second, permanently-null entry under the clean key.
#    workload::initThread() then iterates *every* entry in the map and
#    calls initThread() through each one; the spurious null entry (sorting
#    before its \r-suffixed twin) null-derefs, immediately after "TPCC
#    schema initialized". This was root-caused by adding temporary
#    diagnostic std::cout lines directly around the map's insertion/lookup
#    sites (a plain gdb backtrace alone only shows `this=0x0`, with no
#    visibility into *which* entry or *why*) and watching the pointer for
#    CUSTOMER_ID_IDX flip from valid to a `.find()` miss mid-parse. Fixed:
#    step 1 below overlays patches/setbench-tpcc/ (CRLF-clean copies of
#    every macrobench/benchmarks/*.txt) on top of the freshly-copied vendor
#    source, the same way rocksdb_experiment.sh strips CRLF from RocksDB's
#    build_tools/*. A durable fix, not a one-time workaround -- it protects
#    against every future Windows checkout of the submodule reintroducing
#    the corruption.
#
# 3. Two more real, independent bugs found and fixed along the way (neither
#    was the SIGSEGV's actual cause, but both were genuinely wrong):
#      - Runtime CLI flags: setbench/DBx1000's arg parser (system/
#        parser.cpp) requires CONCATENATED single-token flags ("-t24"), not
#        "-t" "24" as two argv entries -- this script used to pass the
#        latter, silently zeroing g_thread_cnt. Step 6 now passes only
#        `-pin <core-range>`, matching the paper's own reference scripts.
#      - THREAD_CNT (config.h) is a compile-time constant sizing several
#        fixed arrays, not a runtime flag, despite -tINT existing as a
#        parser override for it; and artifact/vendor/setbench was pinned to
#        a commit unrelated to the one the paper actually used (now
#        re-pinned to 5b574d4, see README's vendored-dependencies table).
#        config.h (in patches/setbench-tpcc/) guards THREAD_CNT with
#        #ifndef and derives NUM_WH from it (warehouses = threads), and
#        step 5 passes -DTHREAD_CNT=${THREADS} through the Makefile's
#        xargs extension hook.
#
# 4. compile.sh (patches/setbench-tpcc/macrobench/compile.sh): had
#    bronson_pext_bst_occ commented out in its algs array, leaving only
#    ellen active -- fixed. Both build in SEPARATE `make clean && make`
#    invocations there (never combined into one), which matters if this
#    script is ever used as sifter.sh's --build driver: `bear` records
#    whatever it wraps into ONE compile_commands.json, and if both data
#    structures' builds landed in the same one, clang-tidy would see
#    macrobench's shared files (wl.cpp, tpcc_wl.cpp, etc.) compiled twice
#    with different -I../ds/<name> flags, producing conflicting fixit
#    replacements for anything both builds touch -- the exact failure mode
#    diagnosed for RocksDB's shared headers when building all of it in one
#    pass (see rocksdb_experiment.sh). This script doesn't invoke compile.sh
#    directly (it calls `make` itself, once per data structure, in fully
#    separate script invocations with separate output directories), so it
#    isn't exposed to this either way, but it's the reason "separate steps"
#    matters here at all.
#
# 5. artifact/vendor/setbench's tracked content on its own doesn't have
#    everything needed either: patches/setbench-tpcc/ additionally carries
#    ~20 files copied verbatim from the paper authors' own reference
#    checkout (macrobench/* and ds/{ellen_ext_bst_lf,bronson_pext_bst_occ}/*)
#    -- real functional fixes that exist only as local, uncommitted patches
#    in that reference tree, not in any commit reachable from setbench's
#    own upstream history (e.g. ellen_impl.h's `recmgr->template
#    deallocate(...)` disambiguation, and several
#    `#if defined(MACROBENCH_SINGLE_RECMGR)`-gated alternate constructors in
#    the adapters/index layer). None of them turned out to be the SIGSEGV's
#    cause (confirmed: it reproduced identically with or without them), but
#    they're kept because they're genuine correctness fixes the paper
#    relied on. See the vendored-dependencies table in artifact/README.md
#    for why these live in a plain superproject directory, applied at
#    runtime, rather than committed inside the submodule itself.
#
# For the record, dead ends chased and ruled out along the way: allocator
# choice (LD_PRELOADing jemalloc/mimalloc made no difference either way);
# CPU pin range (this dev machine's Docker Desktop only exposes 16 CPUs, so
# `-pin 0-23` was itself invalid there, but fixing that alone didn't stop
# the crash); and TPCC_SMALL, setbench's own faster-populating reduced
# table size, investigated as a speed-up for local testing and abandoned --
# see the TPCC_SMALL comment below for why.
#
# Remaining gap: only tested at THREADS=2 (both data structures, full run
# to completion) and THREADS=16/24 (reached and ran well past schema init,
# no crash, but not timed to full completion in this pass -- the
# instrumented binary is measurably slower than stock, since memhook logs
# every allocation). The fixes above are structurally thread-count-
# independent (schema loading only depends on the schema file being
# correct and complete, not on thread count), so there's no specific reason
# to expect THREADS=24 (the paper-matching default) to behave differently,
# but it hasn't been separately run to completion to confirm that.
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
    local WORK="$SIFTER_ROOT/artifact/experiments/${out_name}/work"
    local SRC_COPY="${WORK}/src"
    local INSTRUMENTED="${WORK}/instrumented"
    local MEMHOOK_DIR="$SIFTER_ROOT/memhook"
    local MB_SUBDIR="macrobench"

    # Paper Section 6.3: TPC-C OLTP workload via db_bench-equivalent
    # (setbench's own rundb_TPCC_* harness). THREAD_CNT is compiled in (see
    # STATUS above); NUM_WH tracks it 1:1 (warehouses = threads, the
    # standard low-contention TPC-C config, via config.h), matching the
    # paper's reference run scripts, which only ever pass -pin and never
    # override warehouse count separately.
    #
    # Defaults below (THREADS=2, RUN_SECONDS=10) are deliberately small and
    # match exactly what's been verified to run to full completion (see
    # STATUS above) -- this experiment's purpose in this artifact is to
    # demonstrate HeapLENS's instrumentation/sampling/visualization pipeline
    # working end-to-end on the paper's actual TPC-C case study, not to
    # reproduce Table 1's throughput numbers (which would need the paper's
    # follow-up code fix applied too; see "Diagnostic finding only" in
    # artifact/README.md). Warehouse count scales 1:1 with THREADS, and
    # per-warehouse population dominates wall-clock time far more than
    # RUN_SECONDS does, so THREADS is the main lever if you want a bigger
    # (or the paper-matching THREADS=24) run -- e.g. `THREADS=24
    # RUN_SECONDS=30 artifact/experiments/tpcc_efrb/run.sh`. That's been
    # confirmed to build and run well past schema init with no crash, just
    # not separately timed to full completion here.
    local THREADS="${THREADS:-2}"
    local RUN_SECONDS="${RUN_SECONDS:-10}"

    local SAMPLE_PROPORTION="${SAMPLE_PROPORTION:-0.2}"
    local PAGES_PER_TYPE="${PAGES_PER_TYPE:-4}"

    # (TPCC_SMALL, setbench's own flag for a faster-populating reduced
    # table size, was investigated as a speed-up for local testing here and
    # abandoned: beyond an incomplete TPCC_short_schema.txt -- missing 4 of
    # 10 Index= declarations, itself fixable, see git history -- it also
    # hits a pthread mutex assertion failure elsewhere that looks like a
    # genuine, separate upstream concurrency bug in that same under-tested
    # code path. Not worth chasing for a testing convenience the paper's
    # own methodology never uses; use a smaller THREADS value with the full
    # schema instead if you need a faster local iteration loop -- warehouse
    # count tracks THREADS 1:1, so e.g. THREADS=2 populates far less data
    # while still exercising the real, paper-faithful schema and code path.)

    echo "=== [$out_name] 1/7: fresh working copy of setbench (with submodules) ==="
    rm -rf "$WORK"
    mkdir -p "$WORK"
    cp -r "$SETBENCH_SRC" "$SRC_COPY"
    if [ ! -e "$SRC_COPY/common/recordmgr/allocator_bump.h" ]; then
        echo "ERROR: common/recordmgr submodule not initialized in artifact/vendor/setbench." >&2
        echo "Run: git -C artifact/vendor/setbench submodule update --init common/recordmgr tools" >&2
        exit 1
    fi
    mkdir -p "$SRC_COPY/$MB_SUBDIR/bin"
    # Overlay artifact/patches/setbench-tpcc/ on top of the freshly-copied
    # vendor source. This is deliberately a plain superproject directory,
    # NOT a change committed inside the setbench submodule itself: anything
    # only committed in the submodule's own working tree would silently
    # vanish the moment anyone (including this repo's own setup.sh) runs
    # `git submodule update`, since submodules are tracked by commit SHA,
    # not working-tree state, and these particular fixes were never pushed
    # to setbench's upstream remote (they only exist as uncommitted local
    # changes in the paper authors' own reference checkout, which is not
    # part of this repo). Keeping them here instead makes the fix survive a
    # completely fresh `git clone --recurse-submodules` with no extra steps.
    # Two independent things live under here, both required (see the
    # STATUS comment above for the full root-cause writeup):
    #   - macrobench/benchmarks/*.txt: CRLF-cleaned schema data files. A
    #     Windows checkout of the setbench submodule (core.autocrlf=true)
    #     corrupts these -- no .gitattributes rule protects them (those
    #     only cover scripts, not data files). getline()'s failure to strip
    #     \r then causes index names parsed from here to silently mismatch
    #     their clean-string-literal lookups elsewhere (e.g.
    #     "CUSTOMER_ID_IDX\r" vs "CUSTOMER_ID_IDX"), which
    #     std::map::operator[] resolves by silently inserting a
    #     permanently-null entry under the clean key -- this is the actual
    #     SIGSEGV fix.
    #   - The other ~20 files (macrobench/*, ds/{ellen_ext_bst_lf,
    #     bronson_pext_bst_occ}/*): real functional fixes from the paper
    #     authors' own checkout that exist only as uncommitted local
    #     patches there, not in any commit reachable from setbench's
    #     upstream history. These were not the SIGSEGV's cause (confirmed:
    #     it reproduced identically with or without them), but they're
    #     genuine correctness fixes the paper relied on and are kept for
    #     that reason.
    cp -r "$SIFTER_ROOT/artifact/patches/setbench-tpcc/." "$SRC_COPY/"

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
        --build "bear -- make workload=TPCC data_structure_name=${ds_name}"

    echo "=== [$out_name] 3/7: apply clang-tidy fixes ==="
    (cd "$INSTRUMENTED" && clang-apply-replacements-14 ./)

    echo "=== [$out_name] 4/7: add memhook_interface.h includes ==="
    ./sifter.sh "$INSTRUMENTED" --includes-only
    # No separate mem_alloc::alloc / config.h patch step here anymore -- both
    # are now baked into artifact/patches/setbench-tpcc/ (system/mem_alloc.h,
    # config.h) and were already applied back in step 1, before clang-tidy
    # ever ran. See that directory's mem_alloc.h for exactly how/why the
    # template overload works (it's guarded on __MEMHOOK_INTERFACE_H, which
    # is only defined post- this --includes-only step, so it's correctly
    # invisible during step 2's clang-tidy analysis pass and only becomes
    # active for this final instrumented build).

    echo "=== [$out_name] 5/7: rebuild target linked against memhook ==="
    (
        cd "$INSTRUMENTED/$MB_SUBDIR"
        make clean workload=TPCC data_structure_name="$ds_name" || true
        # setbench's macrobench/Makefile does a plain `CFLAGS =`/`LDFLAGS =`
        # reset before its own `+=` lines, so neither a `make CFLAGS=...`
        # command-line arg (frozen by Make, makefile's `+=` silently
        # ignored) nor a CFLAGS *environment* variable (wiped out by that
        # plain `=` reset) survives to the actual compile/link. The
        # Makefile has its own purpose-built extension hook instead
        # (`CFLAGS += $(xargs)`, line 16) -- use that. -DTHREAD_CNT=$THREADS
        # is folded in here too (see STATUS above): it's a compile-time
        # constant, not a runtime flag, despite -tINT existing as a runtime
        # override for it (parser.cpp) -- setting only the runtime flag
        # leaves the compiled-in THREAD_CNT=8 default sizing several fixed
        # per-thread arrays too small for more than 8 threads.
        make workload=TPCC data_structure_name="$ds_name" \
            xargs="-DTHREAD_CNT=${THREADS} -I${MEMHOOK_DIR} -L${MEMHOOK_DIR} -Wl,-rpath=${MEMHOOK_DIR} -lmemhook -ldl"
    )

    echo "=== [$out_name] 6/7: run instrumented TPC-C benchmark ==="
    echo "    threads=$THREADS warehouses=$THREADS (NUM_WH tracks THREAD_CNT, see patches/setbench-tpcc/macrobench/config.h)"
    (
        cd "$INSTRUMENTED/$MB_SUBDIR"
        # -pin takes a literal core-range string (system/thread_pinning.h),
        # e.g. "0-23" for 24 threads -- NOT "-t"/"-n" as separate argv
        # tokens (see STATUS above for why that silently zeroed g_thread_cnt).
        # The +300s grace margin (well beyond RUN_SECONDS, the workload's own
        # internal timed phase) is deliberately generous: memhook logs every
        # single allocation, and warehouse/table population alone -- before
        # the timed workload phase even starts -- is measurably slower under
        # instrumentation than the stock build. A `timeout`-triggered kill
        # here looks identical to a hang from the caller's perspective (both
        # just stop producing output), so err on the side of more time rather
        # than risk mistaking "still working" for "stuck".
        timeout "$((RUN_SECONDS + 300))" \
            "./bin/rundb_TPCC_${ds_name}" -pin "0-$((THREADS - 1))"
    )
    # Expected outputs in $INSTRUMENTED/$MB_SUBDIR: binary_dump.txt,
    # fileset_dump.txt, typeset_dump.txt, fielddump.txt

    echo "=== [$out_name] 7/7: sample into sqlite database ==="
    cd "$SIFTER_ROOT"
    ./sifter.sh "$INSTRUMENTED" -d -s "$MB_SUBDIR" \
        --sample "$SAMPLE_PROPORTION" \
        --pages-per-type "$PAGES_PER_TYPE" \
        --field-dump fielddump.txt \
        --page-size 2097152

    local RESULT_DB="$SIFTER_ROOT/artifact/experiments/${out_name}/${out_name}.sqlite"
    cp "$SIFTER_ROOT/type_analysis/allocs.sqlite" "$RESULT_DB"
    echo "=== [$out_name] done. Database: $RESULT_DB ==="
    echo "    Open it in the visualizer in huge-page mode to inspect segregation of"
    echo "    data-structure nodes vs. database rows (cf. paper Figure 6)."
}
