#!/usr/bin/env bash
# Throughput and raw whole-process counters. Counts / (operations/second)
# is NOT events/operation; do not describe these counters as such.
set -euo pipefail
PERFBENCH_EVENTS="${PERFBENCH_EVENTS:-cache-misses,page-faults,L1-dcache-load-misses,LLC-load-misses,LLC-store-misses,context-switches,dTLB-load-misses}"

perfbench_init_results() {
    mkdir -p "$(dirname "$1")"
    printf 'variant\tthreads\trun\tthroughput_ops_s\tcache_misses_raw\tpage_faults_raw\tl1d_misses_raw\tllc_load_misses_raw\tllc_store_misses_raw\tcontext_switches_raw\tdtlb_misses_raw\n' > "$1"
}

perfbench_run_rep() {
    local results="$1" run_dir="$2" variant="$3" threads="$4" run_idx="$5" pattern="$6" multiplier="$7"
    shift 7
    [[ "$1" == -- ]] && shift
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
    local raw throughput
    raw="$(grep -oP "$pattern" "$log" | tail -1)"
    [[ -n "$raw" ]] || { echo "No throughput in $log" >&2; return 1; }
    throughput="$(awk -v x="$raw" -v m="$multiplier" 'BEGIN {printf "%.4f", x*m}')"
    awk -v t="$throughput" 'BEGIN {exit !(t>0)}' || { echo "Invalid throughput" >&2; return 1; }
    event_count() {
        awk -F, -v ev="$1" '
          {gsub(/^[ \t]+|[ \t]+$/, "", $1); gsub(/^[ \t]+|[ \t]+$/, "", $3)}
          $3==ev && $1 ~ /^[0-9]+([.][0-9]+)?$/ {print $1; found=1; exit}
          END {if (!found) print "NA"}' "$stats"
    }
    printf '%s\t%s\t%s\t%s' "$variant" "$threads" "$run_idx" "$throughput" >> "$results"
    for ev in cache-misses page-faults L1-dcache-load-misses LLC-load-misses LLC-store-misses context-switches dTLB-load-misses; do
        printf '\t%s' "$(event_count "$ev")" >> "$results"
    done
    printf '\n' >> "$results"
    echo "  $variant repetition $run_idx: $throughput operations/s"
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
        echo "Counter columns are RAW whole-process totals, including initialization/prefill."
        echo "They are NOT the paper's measurement-window events/operation. Unavailable/disabled events are NA."
        echo "Per-run results and logs: $results"
    } | tee "$summary"
}
