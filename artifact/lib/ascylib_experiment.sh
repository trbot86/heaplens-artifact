#!/usr/bin/env bash
# Shared driver for the ASCYLIB diagnostic experiments (EFRB / DVY / HJ trees,
# HeapLENS paper Section 6.2 and Appendix B / Table 1 rows 1-3).
#
# TRACE_VARIANT=baseline (default) or optimized selects before/after layouts.
# EFRB also accepts segregation-only and prefill-only (Figure 5b).
# These instrumented runs generate diagnostic databases. Use the corresponding
# *_bench command for uninstrumented throughput and hardware counters.
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
    make_args+=(SET_CPU=0)
    local variant="${TRACE_VARIANT:-baseline}"
    if [[ "$out_name" == ascylib_efrb ]]; then
        case "$variant" in
            baseline) ;;
            segregation-only) make_args+=(SEG_OBJS=1) ;;
            prefill-only) make_args+=(INIT=all) ;;
            optimized) make_args+=(SEG_OBJS=1 INIT=all) ;;
            *) echo "Unknown EFRB TRACE_VARIANT: $variant" >&2; return 2 ;;
        esac
    elif [[ "$variant" == optimized ]]; then
        case "$out_name" in
            ascylib_dvy) make_args+=(DRACHSLER_PAD=192 VERSION=O2) ;;
            ascylib_hj) ;; # Runtime allocator change, below.
        esac
    elif [[ "$variant" != baseline ]]; then
        echo "Unknown TRACE_VARIANT: $variant" >&2; return 2
    fi
    [[ "$out_name" != ascylib_dvy || "$variant" != baseline ]] || make_args+=(VERSION=O2)

    local SIFTER_ROOT
    SIFTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    local ASCYLIB_SRC="$SIFTER_ROOT/artifact/vendor/ascylib"
    local RUN_ROOT="${ARTIFACT_RUN_DIR:-$SIFTER_ROOT/artifact/experiments/${out_name}}"
    local WORK="$RUN_ROOT/work"
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
    local PAGES_PER_TYPE="${PAGES_PER_TYPE:-1}"

    echo "=== [$out_name] 1/7: fresh working copy of ASCYLIB ==="
    [[ ! -e "$WORK" ]] || { echo "Refusing to overwrite $WORK" >&2; return 1; }
    mkdir -p "$WORK"
    python3 - "$RUN_ROOT/trace-configuration.json" "$variant" "$THREADS" "$INITIAL" "$RANGE" "$DURATION_MS" "$UPDATE_PCT" "${make_args[@]}" <<'PY'
import json, sys
from pathlib import Path
path, variant, threads, initial, key_range, duration_ms, update_pct, *flags = sys.argv[1:]
Path(path).write_text(json.dumps({
    "variant": variant, "make_arguments": flags, "threads": int(threads),
    "initial": int(initial), "range": int(key_range),
    "duration_ms": int(duration_ms), "update_pct": int(update_pct)
}, indent=2) + "\n")
PY
    cp -r "$ASCYLIB_SRC" "$SRC_COPY"
    source "$SIFTER_ROOT/artifact/lib/prepare_ascylib.sh"
    prepare_ascylib "$SIFTER_ROOT" "$SRC_COPY"
    local SSMEM_LIB_DIR="$WORK/trace-ssmem"
    prepare_ascylib_trace_ssmem "$SIFTER_ROOT" "$SSMEM_LIB_DIR"
    # Clang rejects GCC's legacy cast-as-lvalue assembly output operands.
    patch --batch --directory "$SRC_COPY" -p1 -i "$SIFTER_ROOT/artifact/patches/ascylib-clang14.patch"

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
        --build "env CFLAGS=-fno-pie LDFLAGS='-no-pie -L${SSMEM_LIB_DIR} -Wl,-rpath=${SSMEM_LIB_DIR}' bear -- make ${make_args[*]}"

    echo "=== [$out_name] 3/7: apply clang-tidy fixes ==="
    (cd "$INSTRUMENTED" && clang-apply-replacements-14 ./)
    test -s "$INSTRUMENTED/$tree_src_dir/typeset_dump.txt"
    test -s "$INSTRUMENTED/$tree_src_dir/fileset_dump.txt"

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
        LDFLAGS="-no-pie -L${SSMEM_LIB_DIR} -Wl,-rpath=${SSMEM_LIB_DIR} -L${MEMHOOK_DIR} -Wl,-rpath=${MEMHOOK_DIR} -lmemhook -ldl" \
        make "${make_args[@]}"
    )

    # Fail before collecting a misleading trace if static linking returns.
    python3 - "$INSTRUMENTED/bin/$binary_name" "$SSMEM_LIB_DIR/libssmem_x86_64.so" "$RUN_ROOT/ssmem-linkage.json" <<'PY'
import hashlib, json, subprocess, sys
from pathlib import Path
binary, library, receipt = map(Path, sys.argv[1:])
linked = subprocess.check_output(['ldd', str(binary)], text=True)
if str(library) not in linked:
    raise RuntimeError('Diagnostic binary must load the recorded shared SSMEM library')
symbols = subprocess.check_output(['nm', '-D', str(binary)], text=True)
if not any(line.split() == ['U', 'ssmem_free'] for line in symbols.splitlines()):
    raise RuntimeError('Diagnostic ssmem_free must remain interposable')
Path(receipt).write_text(json.dumps({'library': str(library),
    'library_sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
    'ssmem_free': 'undefined dynamic symbol; memhook intercepts retirements',
    'ldd': linked}, indent=2) + '\n')
PY

    echo "=== [$out_name] 6/7: run instrumented benchmark ==="
    echo "    threads=$THREADS initial=$INITIAL range=$RANGE duration_ms=$DURATION_MS update%=$UPDATE_PCT"
    (
        cd "$INSTRUMENTED/$tree_src_dir"
        # ASCYLIB's own Makefile.common puts binaries in <ascylib-root>/bin/
        # (BINDIR ?= $(ROOT)/bin, ROOT ?= ../..), not <tree-dir>/bin/.
        local preload="$MEMHOOK_DIR/libmemhook.so"
        # HJ's improvement replaces jemalloc backing with glibc malloc.
        if [[ "$out_name" == ascylib_hj && "$variant" == baseline ]]; then
            preload+=":$SIFTER_ROOT/artifact/vendor/heaplens-allocators/libjemalloc-heaplens.so"
        fi
        LD_PRELOAD="$preload" "../../bin/${binary_name}" -i "$INITIAL" -r "$RANGE" -n "$THREADS" -u "$UPDATE_PCT" -d "$DURATION_MS"
    )
    # Expected outputs in $INSTRUMENTED/$tree_src_dir: binary_dump.txt,
    # fileset_dump.txt, typeset_dump.txt, fielddump.txt

    echo "=== [$out_name] 7/7: sample into sqlite database ==="
    cd "$SIFTER_ROOT"
    ./sifter.sh "$INSTRUMENTED" -d -s "$tree_src_dir" \
        --sample "$SAMPLE_PROPORTION" \
        --pages-per-type "$PAGES_PER_TYPE" \
        --field-dump fielddump.txt

    local RESULT_DB="$RUN_ROOT/${out_name}.sqlite"
    cp "$SIFTER_ROOT/type_analysis/allocs.sqlite" "$RESULT_DB"
    python3 "$SIFTER_ROOT/artifact/check_database.py" "$RESULT_DB"
    echo "=== [$out_name] done. Database: $RESULT_DB ==="
    echo "    Open it in the visualizer (sifter_vis_d3/sifter) to inspect cache-set"
    echo "    occupancy / page layout and compare qualitatively against the paper's figures."
}
