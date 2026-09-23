#!/usr/bin/env bash
# Runs HeapLENS's LLM-friendly data exporter (paper Appendix D:
# sifter_vis_d3/server/export_page_snapshots.py) against a HeapLENS
# .sqlite database, producing the compact/analysis text an LLM agent would
# be fed for automated memory-layout diagnosis -- the tool used for the
# paper's Valkey/HNSWLib LLM case studies (not otherwise scripted in this
# artifact; see artifact/README.md).
#
# Run this on the HOST, not inside docker/ubuntu_22_04: export_page_
# snapshots.py imports sampler.py (the same page-clustering code the
# visualizer backend uses for its own sampling), which needs scikit-learn/
# pandas/numpy/matplotlib -- not part of the Docker image (sifter_vis_d3/
# is excluded via .dockerignore; the C++ instrumentation toolchain doesn't
# need it). Set up the same Python virtual environment the root README's
# "Step 3: Visualization" describes first, if you haven't already:
#   python -m venv /path/to/venv && source /path/to/venv/bin/activate
#   pip install -r sifter_vis_d3/server/requirements.txt
#
# Usage: artifact/export_llm_data.sh [db.sqlite] [output_dir]
#   db.sqlite   any HeapLENS-sampled database; defaults to
#               artifact/experiments/ascylib_efrb/ascylib_efrb.sqlite (run
#               that experiment inside docker/ubuntu_22_04 first if it
#               doesn't exist yet, then copy the .sqlite out to the host)
#   output_dir  defaults to a llm_export/ directory next to the database
set -euo pipefail
SIFTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DB="${1:-$SIFTER_ROOT/artifact/experiments/ascylib_efrb/ascylib_efrb.sqlite}"

if [ ! -f "$DB" ]; then
    echo "ERROR: $DB does not exist." >&2
    echo "       Run the experiment that produces it first (inside" >&2
    echo "       docker/ubuntu_22_04), e.g.:" >&2
    echo "       artifact/experiments/ascylib_efrb/run.sh" >&2
    exit 1
fi

OUTPUT_DIR="${2:-$(cd "$(dirname "$DB")" && pwd)/llm_export}"

(cd "$SIFTER_ROOT/sifter_vis_d3/server" && python3 export_page_snapshots.py "$DB" "$OUTPUT_DIR")
