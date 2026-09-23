#!/usr/bin/env bash
# Throughput, raw whole-process counters, and counters per benchmark operation.
# Counters include initialization/prefill; denominators count measured operations.
set -euo pipefail
PERFBENCH_EVENTS="${PERFBENCH_EVENTS:-cache-misses,page-faults,L1-dcache-load-misses,LLC-load-misses,LLC-store-misses,context-switches,dTLB-load-misses}"
PERFBENCH_RESULTS_PY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/perfstat_results.py"

perfbench_init_results() {
    mkdir -p "$(dirname "$1")"
    python3 "$PERFBENCH_RESULTS_PY" header > "$1"
}

perfbench_run_rep() {
    local results="$1" run_dir="$2" variant="$3" threads="$4" run_idx="$5" benchmark="$6"
    shift 6
    [[ "$1" == -- ]] || { echo "Expected -- before benchmark command" >&2; return 1; }
    shift
    mkdir -p "$run_dir"
    local stats="$run_dir/perf.${variant}.t${threads}.r${run_idx}.csv"
    local log="$run_dir/stdout.${variant}.t${threads}.r${run_idx}.log"
    printf '%q ' "$@" > "$log.command"
    if [[ "${PERFBENCH_PERF:-on}" == off ]]; then
        "$@" > "$log" 2>&1 || { tail -30 "$log" >&2; return 1; }
        : > "$stats"
    else
        perf stat -x, -e "$PERFBENCH_EVENTS" -o "$stats" -- "$@" > "$log" 2>&1 || {
            echo "Benchmark/perf failed; inspect $log and $stats. For throughput-only rerun explicitly set PERFBENCH_PERF=off." >&2
            tail -30 "$log" >&2
            return 1
        }
    fi
    python3 "$PERFBENCH_RESULTS_PY" append --benchmark "$benchmark" \
        --results "$results" --log "$log" --perf "$stats" \
        --variant "$variant" --threads "$threads" --run "$run_idx"
}

perfbench_print_summary() {
    local results="$1" title="$2" summary="${3:-/dev/null}"
    {
        echo "$title"
        python3 - "$results" <<'PY'
import csv, statistics, sys
groups = {}
with open(sys.argv[1]) as f:
    for row in csv.DictReader(f, delimiter='\t'):
        groups.setdefault((row['variant'], row['threads']), []).append(float(row['throughput_ops_s']))
baselines = {}
for (variant, threads), xs in groups.items():
    mean = statistics.mean(xs)
    baseline = baselines.setdefault(threads, mean)
    sd = f'{statistics.stdev(xs):.2f}' if len(xs) > 1 else 'NA'
    print(f'{variant:28s} threads={threads} n={len(xs)} mean={mean:.2f} ops/s SD={sd} change={100*(mean/baseline-1):+.2f}%')
PY
        echo "Counters include initialization/prefill: *_raw are totals; *_per_op divide by operation_count."
        echo "operation_unit identifies tree operations or committed transactions. Unavailable/disabled events are NA."
        echo "Per-run results and logs: $results"
    } | tee "$summary"
}
