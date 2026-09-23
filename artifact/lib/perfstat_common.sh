#!/usr/bin/env bash
# Shared helpers for the HeapLENS paper's quantitative "before/after" ablation
# experiments (Table 1 rows 1-5, Table 3, Table 4, Table 5): these measure
# raw throughput and hardware-counter miss rates with `perf stat`, comparing
# a stock data structure/config against the paper's fixes. This is DIFFERENT
# from artifact/lib/ascylib_experiment.sh and artifact/lib/tpcc_experiment.sh,
# which drive HeapLENS's own instrumentation/sampling/visualization pipeline
# (memhook + sifter.sh) to produce a sampled .sqlite database for the
# visualizer -- these scripts instead build and run the UNINSTRUMENTED
# benchmark binaries directly under `perf stat`, exactly as the paper's own
# experiments did, and print a human-readable summary table of the results.
#
# One caveat about the hardware counters: cache-misses, LLC-*-misses,
# L1-dcache-load-misses, and dTLB-load-misses all require the host CPU's
# hardware performance-monitoring unit (PMU) to be exposed to the container.
# This is a genuinely different resource than the CAP_SYS_ADMIN / ptrace
# permissions that most "perf in Docker" guides talk about: it requires the
# hypervisor underneath Docker to virtualize/passthrough the PMU MSRs, which
# most Type-2 hypervisors (including Docker Desktop's WSL2/Hyper-V backend on
# Windows, and similarly most cloud VMs without nested virtualization
# enabled) simply do not do. On such a host, `perf stat -e cache-misses ...`
# prints "<not supported>" for EVERY hardware event, even running as root
# with a fully unrestricted /proc/sys/kernel/perf_event_paranoid. This is a
# host/hypervisor limitation, not something any container flag fixes. Software
# events (page-faults, context-switches) are unaffected and always work.
# These scripts detect and clearly report this rather than silently emitting
# zeroes; see perfbench_print_summary below. To capture the actual hardware
# counter values, run these experiments on bare-metal Linux (or a VM with PMU
# passthrough enabled), matching how the paper's own results were captured.

set -euo pipefail

# The exact event set used throughout the paper's ASCYLIB/TPC-C ablation
# scripts (run_experiment_asplos*.sh).
PERFBENCH_EVENTS="cache-misses,page-faults,L1-dcache-load-misses,LLC-load-misses,LLC-store-misses,context-switches,dTLB-load-misses"

# perfbench_init_results <results_tsv>
# Starts a fresh results file with a header row.
perfbench_init_results() {
    local results_tsv="$1"
    mkdir -p "$(dirname "$results_tsv")"
    printf 'variant\tthreads\trun\tthroughput\tcache_miss_rate\tpage_faults\tl1d_load_miss_rate\tllc_load_miss_rate\tllc_store_miss_rate\tcontext_switch_rate\ttlb_load_miss_rate\n' > "$results_tsv"
}

# perfbench_run_rep <results_tsv> <run_dir> <variant> <threads> <run_idx> \
#                    <throughput_pcre_lookbehind> <throughput_multiplier> -- <cmd...>
#
# Runs <cmd...> once under `perf stat -x,` (CSV output, easy/robust to
# parse -- avoids the line-by-line regex matching the original scripts used
# against perf's human-readable table, which is sensitive to perf version
# formatting differences). Appends one row to <results_tsv>.
#
# <throughput_pcre_lookbehind> is a `grep -oP` pattern (e.g.
# '(?<=#Mops )[0-9.]+') applied to the command's stdout to extract the
# throughput value the benchmark itself printed; it is multiplied by
# <throughput_multiplier> (e.g. 1000000 to turn ASCYLIB's "#Mops" into an
# estimated absolute ops/sec figure, 1 to use a value that's already an
# absolute rate like setbench's `throughput=`) before being stored, so that
# every experiment's "throughput" column and every hardware-counter "rate"
# column (= raw event count / throughput) are in the same, genuinely
# per-operation units. This is a more scientifically careful normalization
# than the original run_experiment_asplos*.sh scripts used (they divided
# raw counts directly by whatever value they parsed, which for ASCYLIB was
# the un-scaled #Mops figure) -- relative, cross-variant comparisons are
# unaffected either way, but this keeps the absolute numbers meaningful.
perfbench_run_rep() {
    local results_tsv="$1" run_dir="$2" variant="$3" threads="$4" run_idx="$5"
    local throughput_pcre="$6" throughput_multiplier="$7"
    shift 7
    [ "$1" = "--" ] && shift
    local cmd=("$@")

    mkdir -p "$run_dir"
    local stats_csv="$run_dir/perf.${variant}.t${threads}.r${run_idx}.csv"
    local stdout_log="$run_dir/stdout.${variant}.t${threads}.r${run_idx}.log"

    set +e
    perf stat -x, -e "$PERFBENCH_EVENTS" -o "$stats_csv" -- "${cmd[@]}" > "$stdout_log" 2>&1
    local rc=$?
    set -e
    if [ $rc -ne 0 ]; then
        echo "    !!! run failed (exit $rc): ${cmd[*]}" >&2
        echo "    !!! see $stdout_log" >&2
        return 1
    fi

    local throughput_raw throughput
    throughput_raw="$(grep -oP "$throughput_pcre" "$stdout_log" | tail -1)"
    if [ -z "$throughput_raw" ]; then
        echo "    !!! could not find throughput in $stdout_log (pattern: $throughput_pcre)" >&2
        return 1
    fi
    throughput="$(awk -v v="$throughput_raw" -v m="$throughput_multiplier" 'BEGIN{printf "%.4f", v*m}')"

    # perf -x, CSV columns: value,unit,event,run_time_ns,pct_running,...
    perfbench_event_count() {
        awk -F, -v ev="$1" '$3 ~ ev {print $1; exit}' "$stats_csv"
    }
    local cache_misses page_faults l1d_misses llc_load_misses llc_store_misses ctx_switches tlb_misses
    cache_misses="$(perfbench_event_count 'cache-misses')"
    page_faults="$(perfbench_event_count 'page-faults')"
    l1d_misses="$(perfbench_event_count 'L1-dcache-load-misses')"
    llc_load_misses="$(perfbench_event_count 'LLC-load-misses')"
    llc_store_misses="$(perfbench_event_count 'LLC-store-misses')"
    ctx_switches="$(perfbench_event_count 'context-switches')"
    tlb_misses="$(perfbench_event_count 'dTLB-load-misses')"

    # Turn a raw event count + throughput value into a "rate", or the
    # sentinel "NA" if the event wasn't supported (no hardware PMU access --
    # see the file header) or throughput was zero.
    perfbench_rate() {
        local count="$1"
        if [ -z "$count" ] || [ "$count" = "<not" ] || [ "$count" = "<not supported>" ]; then
            echo "NA"
        else
            awk -v c="$count" -v t="$throughput" 'BEGIN { if (t+0==0) print "NA"; else printf "%.6f", c/t }'
        fi
    }

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$variant" "$threads" "$run_idx" "$throughput" \
        "$(perfbench_rate "$cache_misses")" \
        "${page_faults:-NA}" \
        "$(perfbench_rate "$l1d_misses")" \
        "$(perfbench_rate "$llc_load_misses")" \
        "$(perfbench_rate "$llc_store_misses")" \
        "$(perfbench_rate "$ctx_switches")" \
        "$(perfbench_rate "$tlb_misses")" \
        >> "$results_tsv"

    echo "    run $run_idx: throughput=$throughput cache_miss_rate=$(perfbench_rate "$cache_misses") tlb_load_miss_rate=$(perfbench_rate "$tlb_misses")"
}

# perfbench_print_summary <results_tsv> <title> [summary_out_file]
# Groups rows by (variant, threads) and prints mean throughput + mean rates,
# human-readable, to stdout and (if given) to a file.
perfbench_print_summary() {
    local results_tsv="$1" title="$2" summary_out="${3:-}"

    local body
    body="$(awk -F'\t' '
        NR==1 { next }
        {
            key = $1 "\t" $2
            n[key]++
            thr[key] += $4
            if ($5 != "NA") { cm[key] += $5; cmN[key]++ }
            pf[key] += $6
            if ($7 != "NA") { l1[key] += $7; l1N[key]++ }
            if ($8 != "NA") { llcl[key] += $8; llclN[key]++ }
            if ($9 != "NA") { llcs[key] += $9; llcsN[key]++ }
            cs[key] += $10
            if ($11 != "NA") { tlb[key] += $11; tlbN[key]++ }
            if (!seen[key]++) order[++nk] = key
        }
        END {
            printf "%-28s %8s %6s %16s %16s %10s\n", "variant", "threads", "runs", "throughput(ops/s)", "cache_miss_rate", "tlb_miss_rate"
            for (i = 1; i <= nk; i++) {
                key = order[i]
                split(key, parts, "\t")
                cmv = (cmN[key] > 0) ? sprintf("%.5f", cm[key]/cmN[key]) : "NA (no PMU)"
                tlbv = (tlbN[key] > 0) ? sprintf("%.5f", tlb[key]/tlbN[key]) : "NA (no PMU)"
                mean_thr = thr[key]/n[key]
                if (mean_thr >= 1000000) thrv = sprintf("%.3fM", mean_thr/1000000)
                else if (mean_thr >= 1000) thrv = sprintf("%.2fK", mean_thr/1000)
                else thrv = sprintf("%.2f", mean_thr)
                printf "%-28s %8s %6d %16s %16s %10s\n", parts[1], parts[2], n[key], thrv, cmv, tlbv
            }
        }
    ' "$results_tsv")"

    {
        echo "=== $title ==="
        echo "$body"
        echo
        echo "(Full per-run data, including page-fault/context-switch/L1d/LLC rates: $results_tsv)"
        if awk -F'\t' 'NR>1 && $5=="NA" {found=1} END{exit !found}' "$results_tsv"; then
            echo
            echo "NOTE: cache/TLB/LLC miss rates are 'NA (no PMU)' because this host's"
            echo "hardware performance counters are not accessible (perf stat reported"
            echo "'<not supported>' for every hardware event -- typically because the"
            echo "container is running under a hypervisor without PMU passthrough, e.g."
            echo "Docker Desktop on Windows/Mac). Throughput and page-fault/context-switch"
            echo "numbers are real and unaffected. Run on bare-metal Linux (or a VM with"
            echo "PMU passthrough) to capture the hardware-counter columns."
        fi
    } | tee ${summary_out:+"$summary_out"}
}
