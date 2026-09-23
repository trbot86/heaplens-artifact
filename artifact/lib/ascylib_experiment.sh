#!/usr/bin/env bash
# Shared driver for the ASCYLIB diagnostic experiments (EFRB / DVY / HJ trees,
# HeapLENS paper Section 6.2 and Appendix B / Table 1 rows 1-3).
#
# This reproduces the *diagnostic finding* (the HeapLENS-sampled database +
# cache-set-occupancy data that shows e.g. cache set underutilization by
# tree nodes) for the stock, unmodified data structure. It does NOT apply
# the paper's follow-up code fix (separate memory arenas + multithreaded
# prefill) and therefore does NOT reproduce the claimed throughput/
# cache-miss percentages in Table 1 -- only the underlying pattern those
# numbers were computed from. For that, see the corresponding *_bench
# experiment (e.g. ascylib_efrb_bench).
#
# Usage: run_ascylib_experiment <tree-src-dir> <binary-name> <out-name> [make-args...]
#   tree-src-dir : path under artifact/vendor/ascylib, e.g. src/bst-ellen
#   binary-name  : binary produced under <tree-src-dir>/bin, e.g. lf-bst_ellen
#   out-name     : short slug for this experiment's working directories
#   make-args    : extra `make` variables this tree's Makefile needs, e.g.
#                  STM=LOCKFREE for bst-ellen/bst-howley (empty for bst-drachsler)

set -euo pipefail

run_ascylib_experiment() {
    local tree_src_dir="$1"
    local binary_name="$2"
    local out_name="$3"
    shift 3
    local make_args=("$@")

    local SIFTER_ROOT
    SIFTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    local ASCYLIB_SRC="$SIFTER_ROOT/artifact/vendor/ascylib"
    local WORK="$SIFTER_ROOT/artifact/experiments/${out_name}/work"
    local SRC_COPY="${WORK}/src"
    local INSTRUMENTED="${WORK}/instrumented"
    local MEMHOOK_DIR="$SIFTER_ROOT/memhook"

    # Paper Section 6.2 methodology: 24 threads, tree prefilled with 2^18
    # keys, 5s search-only workload. Override via env vars if needed.
    local THREADS="${THREADS:-24}"
    local INITIAL="${INITIAL:-262144}"   # 2^18
    local RANGE="${RANGE:-524288}"       # ASCYLIB convention: 2x initial
    local DURATION_MS="${DURATION_MS:-5000}"
    local UPDATE_PCT="${UPDATE_PCT:-0}"  # search-only

    local SAMPLE_PROPORTION="${SAMPLE_PROPORTION:-1.0}"
    local PAGES_PER_TYPE="${PAGES_PER_TYPE:-4}"

    echo "=== [$out_name] 1/7: fresh working copy of ASCYLIB ==="
    rm -rf "$WORK"
    mkdir -p "$WORK"
    cp -r "$ASCYLIB_SRC" "$SRC_COPY"

    echo "=== [$out_name] 2/7: build instrumentation toolchain + generate fixes.yaml ==="
    # ASCYLIB is plain C -- no -t/--template flag (that's for C++ typeid-based
    # type inference, see README "Step 1: Modify target application").
    # Ubuntu 22.04's gcc defaults to PIE, but ASCYLIB's bundled ssmem static
    # lib (and its own code) predates that and isn't position-independent --
    # link failures like "recompile with -fPIE" without -no-pie/-fno-pie.
    # NOTE: these are passed via `env VAR=... cmd`, scoped to just this build
    # command, NOT as `make CFLAGS=...` command-line args and NOT exported
    # into this script's own environment (which sifter.sh's earlier steps --
    # building clang-tidy-standalone's CMake-based LLVM/clang toolchain --
    # would also inherit, where forcing -fno-pie could break its own link).
    # GNU Make freezes any variable given on ITS command line, silently
    # ignoring the makefile's own `+=` lines for it, which would strip out
    # all of ASCYLIB's real flags (-DLOCKFREE, -I paths, etc). An inherited
    # environment value doesn't have that restriction and composes normally.
    cd "$SIFTER_ROOT"
    ./sifter.sh "$SRC_COPY" "$INSTRUMENTED" \
        -s "$tree_src_dir" \
        --skip-refactor \
        --build "env CFLAGS=-fno-pie LDFLAGS=-no-pie bear -- make ${make_args[*]}"

    echo "=== [$out_name] 3/7: apply clang-tidy fixes ==="
    (cd "$INSTRUMENTED" && clang-apply-replacements-14 ./)

    echo "=== [$out_name] 4/7: add memhook_interface.h includes ==="
    ./sifter.sh "$INSTRUMENTED" --includes-only

    echo "=== [$out_name] 5/7: rebuild memhook with ASCYLIB support, then target ==="
    # ASCYLIB routes almost all of its node allocations through its own
    # ssalloc()/ssmem_alloc() sub-allocators, not raw malloc -- the
    # AllocationLoggingCheck already special-cases these (see MATCH_FUNCTIONS
    # in clang-tidy-standalone/misc/AllocationLoggingCheck.cpp) and rewrites
    # calls to ssalloc_s()/ssmem_alloc_s(), and memhook already ships real
    # implementations of those (memhook.cpp, memhook_interface.h), gated
    # behind -DMEMHOOK_ASCYLIB. sifter.sh's own memhook build step doesn't
    # know to pass that (it's generic across targets), so rebuild it here.
    (cd "$MEMHOOK_DIR" && (make clean || true) && make MEMHOOK_ASCYLIB=1 -j)
    (
        cd "$INSTRUMENTED/$tree_src_dir"
        make clean "${make_args[@]}" || true
        CFLAGS="-fno-pie -DMEMHOOK_ASCYLIB -I${MEMHOOK_DIR}" \
        LDFLAGS="-no-pie -L${MEMHOOK_DIR} -Wl,-rpath=${MEMHOOK_DIR} -lmemhook -ldl" \
        make "${make_args[@]}"
    )

    echo "=== [$out_name] 6/7: run instrumented benchmark ==="
    echo "    threads=$THREADS initial=$INITIAL range=$RANGE duration_ms=$DURATION_MS update%=$UPDATE_PCT"
    (
        cd "$INSTRUMENTED/$tree_src_dir"
        # ASCYLIB's own Makefile.common puts binaries in <ascylib-root>/bin/
        # (BINDIR ?= $(ROOT)/bin, ROOT ?= ../..), not <tree-dir>/bin/.
        "../../bin/${binary_name}" -i "$INITIAL" -r "$RANGE" -n "$THREADS" -u "$UPDATE_PCT" -d "$DURATION_MS"
    )
    # Expected outputs in $INSTRUMENTED/$tree_src_dir: binary_dump.txt,
    # fileset_dump.txt, typeset_dump.txt, fielddump.txt

    echo "=== [$out_name] 7/7: sample into sqlite database ==="
    cd "$SIFTER_ROOT"
    ./sifter.sh "$INSTRUMENTED" -d -s "$tree_src_dir" \
        --sample "$SAMPLE_PROPORTION" \
        --pages-per-type "$PAGES_PER_TYPE" \
        --field-dump fielddump.txt

    local RESULT_DB="$SIFTER_ROOT/artifact/experiments/${out_name}/${out_name}.sqlite"
    cp "$SIFTER_ROOT/type_analysis/allocs.sqlite" "$RESULT_DB"
    echo "=== [$out_name] done. Database: $RESULT_DB ==="
    echo "    Open it in the visualizer (sifter_vis_d3/sifter) to inspect cache-set"
    echo "    occupancy / page layout and compare qualitatively against the paper's figures."
}
