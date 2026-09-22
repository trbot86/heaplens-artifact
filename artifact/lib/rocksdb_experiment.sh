#!/usr/bin/env bash
# Shared driver for the RocksDB HashSkipList memtable diagnostic experiment
# (HeapLENS paper Section 6.4: the fix that shrank HashSkipList's internal
# SkipList "bucket" node from 56B to 48B, upstreamed as
# https://github.com/facebook/rocksdb/pull/13424, commit 0c7e5bd).
#
# SCOPE: like the ASCYLIB/TPC-C experiments (see ascylib_experiment.sh /
# tpcc_experiment.sh for the same caveat), this reproduces the *diagnostic
# finding* -- the HeapLENS-sampled database showing the pre-fix HashSkipList
# bucket's cache/page layout -- for the stock, unmodified data structure. It
# does NOT apply the paper's fix (the prev_/prev_height_ field swap from PR
# #13424) or reproduce a specific before/after size delta; it only produces
# the sampled data the "before" side of that finding was computed from.
# artifact/vendor/rocksdb is pinned to 7e272d20 (0c7e5bd's PARENT commit),
# i.e. the commit immediately BEFORE the fix landed, deliberately -- that's
# what makes this the "before" (unfixed) diagnostic case.
#
# STATUS: written from the documented sifter.sh pipeline and RocksDB's
# db_bench source (tools/db_bench_tool.cc, memtable/hash_skiplist_rep.cc,
# memtable/skiplist.h) at the pinned commit, but NOT yet exercised
# end-to-end -- this was authored in an environment without a working
# clang-14/LLVM/Docker toolchain. Run inside docker/ubuntu_22_04 and expect
# to debug, same as the other experiments' initial passes did (see
# artifact/README.md's bug list). In particular:
#   - The "SkipList" PR #13424 shrank (memtable/skiplist.h, the class whose
#     prev_/prev_height_ fields were reordered -- one per non-empty hash
#     bucket in HashSkipListRep, NOT the public InlineSkipList used by the
#     default "skip_list" memtablerep) is allocated as
#     `auto addr = allocator_->AllocateAligned(sizeof(Bucket));` immediately
#     followed by `new (addr) Bucket(...)` (memtable/hash_skiplist_rep.cc,
#     GetInitializedBucket) -- i.e. raw-buffer-then-placement-new, RocksDB's
#     usual C++ idiom. sifter.sh's placement-new logging (CPP_PLACEMENT_NEW,
#     controlled by --no-pnew, ON by default -- unlike the ASCYLIB/TPC-C
#     experiments this is not something we had to opt into) captures the
#     *real* allocated type (the SkipList<...> bucket, or the per-key Node
#     in skiplist.h's NewNode, likewise placement-new'd) straight from each
#     `new (mem) T(...)` expression, regardless of the raw buffer pointer's
#     own (uninformative `char*`) declared type.
#   - Arena::Allocate/AllocateAligned are plain (non-template) *virtual*
#     member functions already targeted by AllocationLoggingCheck's
#     MATCH_FUNCTIONS list (see clang-tidy-standalone/misc/
#     AllocationLoggingCheck.cpp), same as setbench's mem_alloc::alloc --
#     so, like tpcc_experiment.sh step 4.5, a template overload has to be
#     patched into memory/arena.h by hand before the final build (step 5
#     below) or the rewritten call sites (`Allocate<T,line,file>(bytes)`)
#     won't compile. UNLIKE mem_alloc::alloc (which tpcc_experiment.sh
#     redirects straight to memhook_malloc) this patch is a pure passthrough
#     to the real Allocate()/AllocateAligned() override with no logging of
#     its own: every Allocate/AllocateAligned call site found here is
#     immediately placement-new'd (see above), so logging here too would
#     double-log (and mislabel as generic `char`) the same address that the
#     placement-new path already logs correctly-typed.
#   - IMPORTANT, and different in kind from ASCYLIB/setbench: db_bench links
#     essentially the entire RocksDB library, and MATCH_FUNCTIONS matches
#     `Allocate` by bare name across ALL of it, not just Arena. Grepping the
#     pinned tree turns up several other unrelated classes with their own
#     `Allocate` method that clang-tidy will equally try to rewrite call
#     sites for -- e.g. MemTableRep::Allocate(size_t, char**) -> KeyHandle
#     (db/memtable.cc), AllocTracker::Allocate(size_t) -> void
#     (memtable/alloc_tracker.cc, but only ever called as a bare statement,
#     which the var-decl/assignment-only matchers don't touch, so probably
#     safe), and RandomAccessFile/WritableFile::Allocate(offset, len, ...)
#     -> Status/IOStatus (env.cc and friends, an fallocate()-style disk
#     preallocation call with nothing to do with memory allocation at all).
#     Only the Arena overload above is patched here since it's the one the
#     paper's finding is actually about; if the build fails on an
#     unresolved `<T, line, file>` reference against one of these other
#     classes, add a same-shaped passthrough template overload to that
#     class too (or, if it's unused by the fillrandom/HashSkipList path
#     specifically, consider trimming db_bench's build inputs instead of
#     patching every colliding class). This is the kind of iterative
#     compile-fix-recompile work the ASCYLIB/TPC-C bug list documents --
#     expect more of it here given RocksDB's much larger surface area.
#
# Usage: run_rocksdb_experiment
# (single entry point: HashSkipList is the only memtable in scope here)

set -euo pipefail

run_rocksdb_experiment() {
    local out_name="rocksdb_hsl"

    local SIFTER_ROOT
    SIFTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    local ROCKSDB_SRC="$SIFTER_ROOT/artifact/vendor/rocksdb"
    local WORK="$SIFTER_ROOT/artifact/experiments/${out_name}/work"
    local SRC_COPY="${WORK}/src"
    local INSTRUMENTED="${WORK}/instrumented"
    local MEMHOOK_DIR="$SIFTER_ROOT/memhook"

    # HashSkipList == db_bench's "prefix_hash" memtablerep (memtable/
    # hash_skiplist_rep.cc, NewHashSkipListRepFactory). It requires a
    # prefix extractor, which db_bench only installs when -prefix_size > 0
    # (tools/db_bench_tool.cc: prefix_extractor_ is null otherwise, and
    # HashSkipListRep asserts on a null prefix extractor).
    local THREADS="${THREADS:-24}"
    local NUM_KEYS="${NUM_KEYS:-2000000}"
    local VALUE_SIZE="${VALUE_SIZE:-100}"
    local PREFIX_SIZE="${PREFIX_SIZE:-8}"
    local HASH_BUCKET_COUNT="${HASH_BUCKET_COUNT:-1048576}"   # 2^20, db_bench default
    # NOTE: named RUN_SECONDS (not DURATION_SECONDS) to match tpcc_experiment.sh's
    # env var, since artifact/run_all.sh --quick shortens runs via RUN_SECONDS=10.
    local RUN_SECONDS="${RUN_SECONDS:-30}"
    local BENCHMARKS="${BENCHMARKS:-fillrandom}"

    local SAMPLE_PROPORTION="${SAMPLE_PROPORTION:-0.2}"
    local PAGES_PER_TYPE="${PAGES_PER_TYPE:-4}"

    echo "=== [$out_name] 1/7: fresh working copy of RocksDB ==="
    rm -rf "$WORK"
    mkdir -p "$WORK"
    cp -r "$ROCKSDB_SRC" "$SRC_COPY"
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
    # docker/ubuntu_22_04/Dockerfile).
    cd "$SIFTER_ROOT"
    ./sifter.sh "$SRC_COPY" "$INSTRUMENTED" \
        -t \
        --skip-refactor \
        --build "bear -- make PORTABLE=1 DEBUG_LEVEL=0 db_bench -j$(nproc)"

    echo "=== [$out_name] 3/7: apply clang-tidy fixes ==="
    (cd "$INSTRUMENTED" && clang-apply-replacements-14 ./)

    echo "=== [$out_name] 4/7: add memhook_interface.h includes ==="
    ./sifter.sh "$INSTRUMENTED" --includes-only

    echo "=== [$out_name] 4.5/7: patch Arena::Allocate/AllocateAligned with template overloads ==="
    # Pure passthrough to the real (non-template) override -- see the
    # file-header comment above for why this must not log anything itself.
    local ARENA_H="$INSTRUMENTED/memory/arena.h"
    if ! grep -q 'template <typename T, int line, uint16_t filename>' "$ARENA_H"; then
        python3 - "$ARENA_H" <<'PYEOF'
import re, sys

path = sys.argv[1]
with open(path) as f:
    src = f.read()

allocate_decl = "  char* Allocate(size_t bytes) override;\n"
allocate_patch = allocate_decl + '''
  template <typename T, int line, uint16_t filename>
  char* Allocate(size_t bytes) {
    return Allocate(bytes);
  }
'''
assert src.count(allocate_decl) == 1, "Arena::Allocate declaration not found or not unique"
src = src.replace(allocate_decl, allocate_patch, 1)

aligned_decl_re = re.compile(
    r"  char\* AllocateAligned\(size_t bytes, size_t huge_page_size = 0,\n"
    r"\s*Logger\* logger = nullptr\) override;\n"
)
m = aligned_decl_re.search(src)
assert m, "Arena::AllocateAligned declaration not found"
aligned_decl = m.group(0)
aligned_patch = aligned_decl + '''
  template <typename T, int line, uint16_t filename>
  char* AllocateAligned(size_t bytes, size_t huge_page_size = 0,
                        Logger* logger = nullptr) {
    return AllocateAligned(bytes, huge_page_size, logger);
  }
'''
src = src[:m.start()] + aligned_patch + src[m.end():]

with open(path, "w") as f:
    f.write(src)
PYEOF
    fi

    echo "=== [$out_name] 5/7: rebuild db_bench linked against memhook ==="
    (
        cd "$INSTRUMENTED"
        make clean || true
        CXXFLAGS="-I${MEMHOOK_DIR}" \
        LDFLAGS="-L${MEMHOOK_DIR} -Wl,-rpath=${MEMHOOK_DIR} -lmemhook -ldl" \
        make PORTABLE=1 DEBUG_LEVEL=0 db_bench -j"$(nproc)"
    )

    echo "=== [$out_name] 6/7: run instrumented db_bench (HashSkipList memtable) ==="
    echo "    threads=$THREADS num=$NUM_KEYS value_size=$VALUE_SIZE prefix_size=$PREFIX_SIZE hash_bucket_count=$HASH_BUCKET_COUNT duration=${RUN_SECONDS}s"
    (
        cd "$INSTRUMENTED"
        rm -rf /tmp/rocksdb_hsl_bench_db
        ./db_bench \
            --benchmarks="$BENCHMARKS" \
            --memtablerep=prefix_hash \
            --hash_bucket_count="$HASH_BUCKET_COUNT" \
            --prefix_size="$PREFIX_SIZE" \
            --threads="$THREADS" \
            --num="$NUM_KEYS" \
            --value_size="$VALUE_SIZE" \
            --duration="$RUN_SECONDS" \
            --db=/tmp/rocksdb_hsl_bench_db
    )
    # Expected outputs in $INSTRUMENTED: binary_dump.txt, fileset_dump.txt,
    # typeset_dump.txt, fielddump.txt

    echo "=== [$out_name] 7/7: sample into sqlite database ==="
    cd "$SIFTER_ROOT"
    ./sifter.sh "$INSTRUMENTED" -d \
        --sample "$SAMPLE_PROPORTION" \
        --pages-per-type "$PAGES_PER_TYPE" \
        --field-dump fielddump.txt

    local RESULT_DB="$SIFTER_ROOT/artifact/experiments/${out_name}/${out_name}.sqlite"
    cp "$SIFTER_ROOT/type_analysis/allocs.sqlite" "$RESULT_DB"
    echo "=== [$out_name] done. Database: $RESULT_DB ==="
    echo "    Open it in the visualizer (sifter_vis_d3/sifter) to inspect the"
    echo "    HashSkipList bucket/node cache-set occupancy at the pre-fix (56B"
    echo "    bucket) commit, i.e. the 'before' side of PR #13424 / paper Sec 6.4."
}
