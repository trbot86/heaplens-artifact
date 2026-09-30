#!/usr/bin/env bash
# Shared driver for the RocksDB HashSkipList memtable diagnostic experiment
# (HeapLENS paper Section 6.4: the fix that shrank HashSkipList's internal
# SkipList "bucket" node from 56B to 48B, upstreamed as
# https://github.com/facebook/rocksdb/pull/13424, commit 0c7e5bd).
#
# TRACE_VARIANT=baseline (default) uses the upstream pre-fix snapshot;
# optimized applies the field-order change before source instrumentation.
# Both generate diagnostic databases; the performance driver uses its separate
# historical source snapshot and workload.
#
# RocksDB needed considerably more iteration than ASCYLIB/TPC-C to bring up
# (it's a much larger, more interconnected codebase), captured in four
# helper scripts this driver calls in sequence below -- see each one's own
# docstring for the specific mechanism and why it's needed:
#   - dedupe_fixes_yaml.py (step 2.5): some headers are #included by dozens
#     of translation units, each analyzed by clang-tidy independently, so
#     two can propose conflicting MemStamp(...) insertions at the same
#     (file, offset) -- which clang-apply-replacements-14 refuses to
#     resolve on its own.
#   - fixup_anon_namespace_casts.py and fixup_malformed_insertions.py
#     (step 3.5): a handful of insertions the checker produces are outright
#     malformed or the wrong type at RocksDB's scale (anonymous-namespace
#     types, template instantiation edge cases, a couple of identifiers it
#     corrupts outright).
#   - patch_allocate_overloads.py (step 4.5): AllocationLoggingCheck matches
#     `Allocate`/`AllocateAligned` by bare name across the whole codebase,
#     which also catches several classes unrelated to memory allocation;
#     each needs a passthrough template overload to compile.
# Two more RocksDB-specific build flags (see step 2/5 below): -Werror trips
# on a pre-existing warning unrelated to instrumentation
# (DISABLE_WARNING_AS_ERROR works around it, RocksDB's own escape hatch),
# and memhook_interface.h's typeid(T) needs RTTI, which RocksDB disables by
# default at DEBUG_LEVEL=0 (USE_RTTI=1, also RocksDB's own flag).
#
# Usage: run_rocksdb_experiment
# (single entry point: HashSkipList is the only memtable in scope here)

set -euo pipefail

run_rocksdb_experiment() {
    local out_name="${1:-rocksdb_hsl}"
    [[ "$out_name" == rocksdb_hsl || "$out_name" == rocksdb_isl ]] || return 2

    local SIFTER_ROOT
    SIFTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    local ROCKSDB_SRC="$SIFTER_ROOT/artifact/vendor/rocksdb"
    local memtable=prefix_hash
    local layout_flags=()
    if [[ "$out_name" == rocksdb_isl ]]; then
        ROCKSDB_SRC="$SIFTER_ROOT/artifact/vendor/rocksdb-historical"
        memtable=skip_list
    fi
    local RUN_ROOT="${ARTIFACT_RUN_DIR:-$SIFTER_ROOT/artifact/experiments/${out_name}}"
    local WORK="$RUN_ROOT/work"
    local SRC_COPY="${WORK}/src"
    local INSTRUMENTED="${WORK}/instrumented"
    local MEMHOOK_DIR="$SIFTER_ROOT/memhook"
    local LIB_DIR="$SIFTER_ROOT/artifact/lib"

    # HashSkipList == db_bench's "prefix_hash" memtablerep (memtable/
    # hash_skiplist_rep.cc, NewHashSkipListRepFactory). It requires a
    # prefix extractor, which db_bench only installs when -prefix_size > 0
    # (tools/db_bench_tool.cc: prefix_extractor_ is null otherwise, and
    # HashSkipListRep asserts on a null prefix extractor).
    #
    # NUM_KEYS should stay comfortably above HASH_BUCKET_COUNT (a few keys
    # per bucket on average) -- HashSkipListRep only allocates a bucket's
    # SkipList once a hash prefix collides with an existing entry, so too
    # few keys per bucket produces almost no SkipList<Bucket> allocations
    # at all, i.e. nothing to see for the paper's own finding.
    local THREADS="${THREADS:-24}"
    local NUM_KEYS="${NUM_KEYS:-2000000}"
    local VALUE_SIZE="${VALUE_SIZE:-100}"
    local PREFIX_SIZE="${PREFIX_SIZE:-8}"
    local HASH_BUCKET_COUNT="${HASH_BUCKET_COUNT:-1048576}"   # 2^20, db_bench default
    # NOTE: named RUN_SECONDS (not DURATION_SECONDS) to match tpcc_experiment.sh's
    # env var, since artifact/run_all.sh --quick shortens runs via RUN_SECONDS=10.
    local RUN_SECONDS="${RUN_SECONDS:-30}"
    local BENCHMARKS="${BENCHMARKS:-fillrandom}"
    # `make benchmarks -j$(nproc)` has been observed to freeze the Docker
    # host (RocksDB's build is heavy, and clang-tidy's own analysis pass on
    # top of that multiplies memory pressure per parallel job). Default to
    # a small, safe job count; override via BUILD_JOBS if your host can
    # handle more.
    local BUILD_JOBS="${BUILD_JOBS:-${JOBS:-4}}"

    # fillrandom ignores --num once --duration is set (it keeps generating
    # keys for the full duration, cycling through the key space repeatedly
    # rather than stopping at NUM_KEYS) -- so RUN_SECONDS, not NUM_KEYS, is
    # what actually drives event-log size here. At the defaults above this
    # produces tens of millions of sampled allocation events; a much lower
    # SAMPLE_PROPORTION than the ASCYLIB/TPC-C experiments' is needed to
    # keep the resulting .sqlite in the "few hundred MB" range the root
    # README recommends for the visualizer.
    local SAMPLE_PROPORTION="${SAMPLE_PROPORTION:-0.05}"
    local PAGES_PER_TYPE="${PAGES_PER_TYPE:-1}"

    echo "=== [$out_name] 1/7: fresh working copy of RocksDB ==="
    [[ ! -e "$WORK" ]] || { echo "Preserve existing results at $WORK; rerun through artifact/run.sh for a new output directory." >&2; return 1; }
    mkdir -p "$WORK"
    cp -r "$ROCKSDB_SRC" "$SRC_COPY"
    if [[ "$out_name" == rocksdb_isl ]]; then
        patch --batch --directory "$SRC_COPY" -p1 -i "$SIFTER_ROOT/artifact/patches/rocksdb-historical.patch"
    fi
    case "${TRACE_VARIANT:-baseline}" in
        baseline) ;;
        optimized)
            if [[ "$out_name" == rocksdb_isl ]]; then
                layout_flags=(ALIGN_TALL_NODE=3 SEG_TALL_NODE=3)
            else
                python3 "$LIB_DIR/rocksdb_trace_layout.py" "$SRC_COPY"
            fi ;;
        *) echo "Unknown TRACE_VARIANT" >&2; return 2 ;;
    esac
    # Two fixups needed only for RocksDB (ASCYLIB/setbench's Makefiles don't
    # hit either of these):
    #   - A Windows checkout of this repo's own artifact/vendor/rocksdb
    #     submodule (core.autocrlf=true) CRLF-corrupts RocksDB's own shell
    #     scripts (build_tools/build_detect_platform et al) the same way
    #     llvm.sh was corrupted (see artifact/README.md's bug list) -- but
    #     this repo's `*.sh text eol=lf` .gitattributes rule only covers
    #     files tracked directly by the superproject, not a submodule's own
    #     tracked content, so it doesn't reach here. RocksDB's Makefile
    #     shells out to build_detect_platform to generate make_config.mk; a
    #     CRLF'd shebang makes that silently fail (`/usr/bin/env: 'bash\r':
    #     No such file or directory`) and the whole build never gets past
    #     `make: *** No rule to make target 'make_config.mk'`.
    #   - $SRC_COPY/.git is a submodule gitlink FILE pointing at
    #     ../../../.git/modules/artifact/vendor/rocksdb, which only resolves
    #     from inside the *original* artifact/vendor/rocksdb location (and
    #     only if the superproject's own .git is present, which it may not
    #     be -- see artifact/setup.sh). Left in place after `cp -r`, it's a
    #     dangling pointer: RocksDB's Makefile shells out to `git rev-parse
    #     HEAD` etc. (to stamp a version into util/build_version.cc), and a
    #     dangling gitlink makes that a hard `fatal: not a git repository`
    #     instead of the clean "not a repo" case RocksDB's build already
    #     tolerates (e.g. building from a git-less release tarball). Removing
    #     it here reduces to that already-supported case.
    find "$SRC_COPY/build_tools" -type f -print0 2>/dev/null | xargs -0 -r dos2unix -q
    rm -f "$SRC_COPY/.git"

    echo "=== [$out_name] 2/7: build instrumentation toolchain + generate fixes.yaml ==="
    # RocksDB is C++ -- use -t/--template, same as setbench (see README
    # "Step 1: Modify target application"). PORTABLE=1 avoids -march=native
    # (the Docker image's compiler target may not match the host CPU);
    # DEBUG_LEVEL=0 gives an optimized (non-debug-asserts) build, since
    # db_bench's own assertions on hot allocation paths would otherwise
    # dominate the runtime. db_bench needs gflags (libgflags-dev, already in
    # docker/ubuntu_22_04/Dockerfile). DISABLE_WARNING_AS_ERROR and
    # USE_RTTI=1: see the file-header comment above.
    #
    # Build the `db_bench` target specifically, not the aggregate
    # `benchmarks` target (which also builds 6 other tools): one of them,
    # table_reader_bench, pulls in db/db_test_util.o, which fails to
    # compile at this pinned commit with DEBUG_LEVEL=0 (it calls
    # TEST_-prefixed DBImpl methods that only exist when NDEBUG is
    # undefined) -- unrelated to instrumentation, and avoided entirely by
    # not needing that object file. RocksDB's own Makefile builds db_bench
    # the same way for its `release` target.
    cd "$SIFTER_ROOT"
    ./sifter.sh "$SRC_COPY" "$INSTRUMENTED" \
        -t \
        --skip-refactor \
        --build "bear -- make PORTABLE=1 DEBUG_LEVEL=0 DISABLE_WARNING_AS_ERROR=1 USE_RTTI=1 ${layout_flags[*]} db_bench -j${BUILD_JOBS}"

    echo "=== [$out_name] 2.5/7: deduplicate colliding insertions in fixes.yaml ==="
    python3 "$LIB_DIR/dedupe_fixes_yaml.py" "$INSTRUMENTED/fixes.yaml"

    echo "=== [$out_name] 3/7: apply clang-tidy fixes ==="
    (cd "$INSTRUMENTED" && clang-apply-replacements-14 ./)

    echo "=== [$out_name] 3.5/7: fix up malformed/incorrect insertions ==="
    python3 "$LIB_DIR/fixup_anon_namespace_casts.py" "$INSTRUMENTED"
    python3 "$LIB_DIR/fixup_malformed_insertions.py" "$INSTRUMENTED"

    echo "=== [$out_name] 4/7: add memhook_interface.h includes ==="
    ./sifter.sh "$INSTRUMENTED" --includes-only

    echo "=== [$out_name] 4.5/7: patch Allocate-collision classes with passthrough template overloads ==="
    python3 "$LIB_DIR/patch_allocate_overloads.py" "$INSTRUMENTED"
    if [[ "$out_name" == rocksdb_isl ]]; then
        python3 "$LIB_DIR/rocksdb_inline_regions.py" "$INSTRUMENTED"
    fi

    echo "=== [$out_name] 5/7: rebuild db_bench linked against memhook ==="
    (
        cd "$INSTRUMENTED"
        make clean || true
        CXXFLAGS="-I${MEMHOOK_DIR}" \
        LDFLAGS="-L${MEMHOOK_DIR} -Wl,-rpath=${MEMHOOK_DIR} -lmemhook -ldl" \
        make PORTABLE=1 DEBUG_LEVEL=0 DISABLE_WARNING_AS_ERROR=1 USE_RTTI=1 "${layout_flags[@]}" db_bench -j"${BUILD_JOBS}"
    )

    echo "=== [$out_name] 6/7: run instrumented db_bench (HashSkipList memtable) ==="
    echo "    threads=$THREADS num=$NUM_KEYS value_size=$VALUE_SIZE prefix_size=$PREFIX_SIZE hash_bucket_count=$HASH_BUCKET_COUNT duration=${RUN_SECONDS}s"
    # --compression_type=none: this PORTABLE=1 build isn't linked against
    # Snappy (db_bench's own default compressor), so db_bench refuses to
    # open a db with the default settings -- irrelevant to what we're
    # measuring (allocation/layout, not on-disk compression).
    # --allow_concurrent_memtable_write=false: HashSkipListRep doesn't
    # support concurrent memtable writes at all (unlike the default
    # skip_list memtablerep); db_bench's own default of true makes it
    # refuse to open with more than one thread otherwise.
    (
        cd "$INSTRUMENTED"
        ./db_bench \
            --benchmarks="$BENCHMARKS" \
            --memtablerep="$memtable" \
            --hash_bucket_count="$HASH_BUCKET_COUNT" \
            --prefix_size="$PREFIX_SIZE" \
            --threads="$THREADS" \
            --num="$NUM_KEYS" \
            --value_size="$VALUE_SIZE" \
            --duration="$RUN_SECONDS" \
            --compression_type=none \
            --allow_concurrent_memtable_write=false \
            --db="$WORK/benchmark-db"
    )
    # Expected outputs in $INSTRUMENTED: binary_dump.txt, fileset_dump.txt,
    # typeset_dump.txt, fielddump.txt

    echo "=== [$out_name] 7/7: sample into sqlite database ==="
    cd "$SIFTER_ROOT"
    local container_args=()
    if [[ "$out_name" == rocksdb_isl ]]; then container_args=(--use-container); fi
    ./sifter.sh "$INSTRUMENTED" -d \
        --sample "$SAMPLE_PROPORTION" \
        --pages-per-type "$PAGES_PER_TYPE" \
        --field-dump fielddump.txt "${container_args[@]}"

    local RESULT_DB="$RUN_ROOT/${out_name}.sqlite"
    cp "$SIFTER_ROOT/type_analysis/allocs.sqlite" "$RESULT_DB"
    python3 "$SIFTER_ROOT/artifact/check_database.py" "$RESULT_DB"
    if [[ "$out_name" == rocksdb_isl ]]; then
        python3 "$LIB_DIR/rocksdb_inline_regions.py" --verify "$RESULT_DB" "${TRACE_VARIANT:-baseline}"
    fi
    echo "=== [$out_name] done. Database: $RESULT_DB ==="
    echo "    Open it in the visualizer (sifter_vis_d3/sifter) to inspect the"
    echo "    $memtable layout (${TRACE_VARIANT:-baseline} variant)."
    if [[ "$out_name" == rocksdb_hsl ]]; then
        echo "    baseline buckets are 56B; optimized buckets are 48B."
    else
        echo "    optimized uses ALIGN_TALL_NODE=3 SEG_TALL_NODE=3, matching the performance variants."
    fi
}
