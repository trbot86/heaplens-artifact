#!/usr/bin/env bash
# Runs HeapLENS's LLM-friendly data exporter (paper Appendix D:
# sifter_vis_d3/server/export_page_snapshots.py) against a HeapLENS
# .sqlite database, producing the compact/analysis text an LLM agent would
# be fed for automated memory-layout diagnosis -- the tool used for the
# paper's Valkey/HNSWLib LLM case studies (not otherwise scripted in this
# artifact; see artifact/README.md).
#
# Use the artifact Docker image, or a host Python environment with the GUI's
# dependencies. For the latter:
#   python -m venv /path/to/venv && source /path/to/venv/bin/activate
#   pip install -r sifter_vis_d3/server/requirements.txt
#
# Usage: artifact/export_llm_data.sh db.sqlite [output_dir]
#   db.sqlite   a generated database in artifact/results/<name>-<timestamp>/
#   output_dir  defaults to a llm_export/ directory next to the database
set -euo pipefail
SIFTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $# == 0 ]]; then
    echo "Usage: bash artifact/export_llm_data.sh DB.sqlite [output_dir]" >&2
    echo "Use the database path printed by the trace-generation command." >&2
    exit 2
fi
DB="$1"

if [ ! -f "$DB" ]; then
    echo "ERROR: $DB does not exist." >&2
    echo "       Generate a trace with: bash artifact/run.sh experiment ascylib_efrb --profile smoke" >&2
    exit 1
fi

OUTPUT_DIR="${2:-$(cd "$(dirname "$DB")" && pwd)/llm_export}"

(cd "$SIFTER_ROOT/sifter_vis_d3/server" && python3 export_page_snapshots.py "$DB" "$OUTPUT_DIR")
