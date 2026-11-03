#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../../lib/tpcc_experiment.sh"
run_tpcc_experiment howley_int_bst_lf tpcc_hj
