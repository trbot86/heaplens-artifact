"""Report perf totals per actual benchmark operation, not per operation/second.

perf wraps the whole process, including prefill and teardown. ASCYLIB's
denominator includes successful and unsuccessful measured tree operations;
TPC-C's denominator counts committed measured transactions (not aborts).
"""

import argparse
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import sys


EVENTS = (
    ("cache-misses", "cache_misses"),
    ("page-faults", "page_faults"),
    ("L1-dcache-load-misses", "l1d_misses"),
    ("LLC-load-misses", "llc_load_misses"),
    ("LLC-store-misses", "llc_store_misses"),
    ("context-switches", "context_switches"),
    ("dTLB-load-misses", "dtlb_misses"),
)
FIELDS = ["variant", "threads", "run", "throughput_ops_s"] + [
    name + "_raw" for _, name in EVENTS
] + ["operation_count", "operation_unit"] + [
    name + "_per_op" for _, name in EVENTS
]


def one_match(pattern, text, label):
    matches = re.findall(pattern, text, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("Expected exactly one {}; found {}".format(label, len(matches)))
    return matches[0]


def parse_benchmark(text, benchmark):
    if benchmark == "ascylib":
        # In test_simple.c, '#txs' misleadingly prints throughput, not a count.
        # Sum the first (total) column, not the successful-operation column.
        count = sum(int(one_match(
            r"^[ \t]*" + label + r":[ \t]+([0-9]+)[ \t]*\|",
            text, label + " total")) for label in ("srch", "insr", "rems"))
        throughput = Decimal(one_match(
            r"^#Mops[ \t]+([0-9]+(?:\.[0-9]+)?)[ \t]*$",
            text, "#Mops line")) * 1000000
        unit = "tree_operation"
    elif benchmark == "tpcc":
        # There are also per-thread and per-index throughput/operation fields.
        # Only the final global summary supplies committed transaction totals.
        summary = one_match(r"^\[summary\][ \t]+(.+)$", text, "TPC-C summary")
        count = int(one_match(r"(?:^|,)[ \t]*txn_cnt=([0-9]+)(?=,|$)",
                              summary, "summary txn_cnt"))
        throughput = Decimal(one_match(
            r"(?:^|,)[ \t]*throughput=([0-9]+(?:\.[0-9]+)?)(?=,|$)",
            summary, "summary throughput"))
        unit = "committed_transaction"
    else:
        raise ValueError("Unknown benchmark: " + benchmark)
    if count <= 0 or throughput <= 0:
        raise ValueError("Operation count and throughput must both be positive")
    return count, throughput, unit


def parse_counters(text):
    counters = {event: "NA" for event, _ in EVENTS}
    seen = set()
    for record in csv.reader(text.splitlines()):
        if len(record) < 3:
            continue
        value, event = record[0].strip(), record[2].strip()
        if event not in counters:
            continue
        if event in seen:
            raise ValueError("Duplicate perf event: " + event)
        seen.add(event)
        try:
            number = Decimal(value)
        except InvalidOperation:
            continue  # e.g. <not supported> or <not counted>
        if number.is_finite() and number >= 0:
            counters[event] = value
    return counters


def make_row(benchmark, log, perf, variant, threads, run):
    count, throughput, unit = parse_benchmark(log, benchmark)
    counters = parse_counters(perf)
    row = dict(variant=variant, threads=threads, run=run,
               throughput_ops_s=format(throughput, ".4f"),
               operation_count=count, operation_unit=unit)
    for event, name in EVENTS:
        raw = counters[event]
        row[name + "_raw"] = raw
        row[name + "_per_op"] = (
            "NA" if raw == "NA" else format(Decimal(raw) / count, ".10g"))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("header")
    append = sub.add_parser("append")
    append.add_argument("--benchmark", choices=("ascylib", "tpcc"), required=True)
    for name in ("results", "log", "perf", "variant"):
        append.add_argument("--" + name, required=True)
    for name in ("threads", "run"):
        append.add_argument("--" + name, type=int, required=True)
    args = parser.parse_args()
    if args.command == "header":
        csv.writer(sys.stdout, delimiter="\t", lineterminator="\n").writerow(FIELDS)
        return
    try:
        row = make_row(args.benchmark, Path(args.log).read_text(),
                       Path(args.perf).read_text(), args.variant, args.threads, args.run)
        # Validate everything before appending, so a failed parse adds no partial row.
        with open(args.results, newline="") as f:
            if next(csv.reader(f, delimiter="\t"), None) != FIELDS:
                raise ValueError("Results header does not match this counter format")
        with open(args.results, "a", newline="") as f:
            csv.DictWriter(f, FIELDS, delimiter="\t", lineterminator="\n").writerow(row)
        print("  {} repetition {}: {} operations/s; {} {}s".format(
            args.variant, args.run, row["throughput_ops_s"],
            row["operation_count"], row["operation_unit"]))
    except (OSError, ValueError) as exc:
        parser.exit(1, "Counter report failed: {}\n".format(exc))


if __name__ == "__main__":
    main()
