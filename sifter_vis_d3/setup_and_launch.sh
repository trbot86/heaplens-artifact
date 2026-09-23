#!/usr/bin/env bash
# Sets up and runs the HeapLENS visualizer end-to-end (root README's
# "Step 3: Visualization", automated): creates/reuses a Python virtual
# environment, installs the backend's Python dependencies, installs
# Node.js into that same venv via nodeenv if a compatible system node
# isn't already on PATH, installs the frontend's npm dependencies, and
# starts both the Flask backend (http://localhost:5000) and the Next.js
# frontend dev server (http://localhost:3000) in the background. Once it
# prints "ready", just open http://localhost:3000.
#
# Run this on the HOST (or any machine with network access and a C
# compiler, for Node's prebuilt binaries) -- NOT inside
# docker/ubuntu_22_04, which doesn't have sifter_vis_d3/ at all (that
# image is for the C++ instrumentation toolchain only).
#
# Usage: sifter_vis_d3/setup_and_launch.sh [--venv /path/to/venv]
#   Ctrl+C stops both servers.
set -euo pipefail

VIS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$VIS_ROOT/.venv"

while [ $# -gt 0 ]; do
    case $1 in
        --venv)
            VENV_DIR="$2"
            shift
        ;;
    esac
    shift
done

if [ ! -f "$VIS_ROOT/sifter/package.json" ]; then
    echo "ERROR: $VIS_ROOT/sifter/ looks empty (no package.json)." >&2
    echo "       It's a git submodule; initialize it first:" >&2
    echo "       git submodule update --init sifter_vis_d3/sifter" >&2
    exit 1
fi

echo "=== setting up Python virtual environment ($VENV_DIR) ==="
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    if ! python3 -m venv "$VENV_DIR"; then
        echo "ERROR: could not create a Python virtual environment at $VENV_DIR." >&2
        echo "       On Debian/Ubuntu this usually means the venv module isn't" >&2
        echo "       installed; try: sudo apt install python3-venv" >&2
        exit 1
    fi
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "=== installing backend Python dependencies ==="
pip install -q -r "$VIS_ROOT/server/requirements.txt"

echo "=== setting up Node.js ==="
NODE_VERSION_NEEDED="18.18.2"
if command -v node >/dev/null 2>&1; then
    echo "    using node already on PATH ($(node --version))"
else
    echo "    no node on PATH; installing node $NODE_VERSION_NEEDED into the venv"
    nodeenv --python-virtualenv --node "$NODE_VERSION_NEEDED"
fi

echo "=== installing frontend npm dependencies ==="
(cd "$VIS_ROOT/sifter" && npm install)

# Each server is launched via `setsid`, which makes it (and every process
# it goes on to spawn, e.g. npm's own next dev -> node -> next-server
# chain) the leader of a brand new process group. `kill $PID` alone would
# only ever kill that top-level PID and leave its descendants running as
# orphans -- `kill -- -$PID` (a negative PID) targets the whole group.
cleanup() {
    echo
    echo "=== stopping servers ==="
    [ -n "${FLASK_PID:-}" ] && kill -- "-$FLASK_PID" 2>/dev/null
    [ -n "${NEXT_PID:-}" ] && kill -- "-$NEXT_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "=== starting backend (flask, http://localhost:5000) ==="
setsid bash -c "cd '$VIS_ROOT/server' && flask --app server run" &
FLASK_PID=$!

echo "=== starting frontend (next dev, http://localhost:3000) ==="
setsid bash -c "cd '$VIS_ROOT/sifter' && npm run dev" &
NEXT_PID=$!

echo
echo "=== ready -- open http://localhost:3000 in your browser ==="
echo "    Copy a .sqlite database into sifter_vis_d3/ first if you haven't"
echo "    (see artifact/README.md's 'Visualizing results', or the root"
echo "    README's 'Step 3: Visualization' step 7)."
echo "    Press Ctrl+C to stop both servers."

wait
