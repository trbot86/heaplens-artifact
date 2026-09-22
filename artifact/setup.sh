#!/usr/bin/env bash
# One-time setup for the HeapLENS/SIFTER ATC'26 artifact.
# Run this once inside the docker/ubuntu_22_04 container before running any
# experiment under artifact/experiments/.
set -euo pipefail
SIFTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SIFTER_ROOT"

if [ -d .git ] || git rev-parse --git-dir >/dev/null 2>&1; then
    echo "=== initializing vendor submodules (ASCYLIB, setbench + its own submodules, RocksDB) ==="
    git submodule update --init artifact/vendor/ascylib
    git submodule update --init artifact/vendor/setbench
    git -C artifact/vendor/setbench submodule update --init common/recordmgr tools
    git submodule update --init artifact/vendor/rocksdb
else
    # No .git here -- e.g. this tree was `COPY`'d into a Docker image (the
    # Dockerfile's build context excludes .git for faster local rebuilds).
    # The vendored submodule *content* still needs to already be present.
    echo "=== no .git found; assuming vendor/ content was copied in directly ==="
    for d in artifact/vendor/ascylib artifact/vendor/setbench artifact/vendor/setbench/common/recordmgr artifact/vendor/rocksdb; do
        if [ -z "$(ls -A "$d" 2>/dev/null)" ]; then
            echo "ERROR: $d is missing or empty, and there's no .git to fetch it." >&2
            echo "       Run 'git submodule update --init --recursive' on the host before" >&2
            echo "       building the Docker image, or don't exclude .git in .dockerignore." >&2
            exit 1
        fi
    done
fi

echo "=== sanity-checking toolchain (clang-14, bear, sqlite3) ==="
for bin in clang-14 clang-tidy-14 clang-apply-replacements-14 bear sqlite3 cmake; do
    if ! command -v "$bin" >/dev/null 2>&1; then
        echo "WARNING: $bin not found on PATH. This script expects to run inside" >&2
        echo "         docker/ubuntu_22_04 (see docker/ubuntu_22_04/Dockerfile)." >&2
    fi
done

echo "=== setup complete ==="
echo "Next: artifact/run_all.sh, or run a single experiment, e.g."
echo "      artifact/experiments/ascylib_efrb/run.sh"
