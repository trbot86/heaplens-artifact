#!/usr/bin/env python3
import csv
import math
import re
import statistics
import sys
from pathlib import Path


VARIANTS = ("baseline", "vector_soa64", "hugepage", "both")
PATTERN = re.compile(r"block(\d{2})_(baseline|vector_soa64|hugepage|both)\.csv$")


def mean(values):
    return statistics.fmean(values)


def sample_stdev(values):
    return statistics.stdev(values) if len(values) > 1 else 0.0


def pct(value, baseline):
    return 100.0 * (value / baseline - 1.0)


def read_results(run_dir):
    rows = {}
    for path in sorted(run_dir.glob("block??_*.csv")):
        match = PATTERN.match(path.name)
        if not match:
            continue
        block = int(match.group(1))
        variant = match.group(2)
        with path.open(newline="", encoding="utf-8") as handle:
            data = list(csv.DictReader(handle))
        if len(data) != 1:
            raise SystemExit(f"expected one result row in {path}, found {len(data)}")
        key = (block, variant)
        if key in rows:
            raise SystemExit(f"duplicate result: {key}")
        row = data[0]
        row["_path"] = path.name
        rows[key] = row

    expected = {(block, variant) for block in range(1, 11) for variant in VARIANTS}
    missing = sorted(expected - set(rows))
    extra = sorted(set(rows) - expected)
    if missing or extra:
        raise SystemExit(f"incomplete design; missing={missing}, extra={extra}")
    return rows


def numeric(rows, block, variant, field):
    return float(rows[(block, variant)][field])


def write_variant_summary(run_dir, rows):
    fields = (
        "variant",
        "trials",
        "qps_mean",
        "qps_median",
        "qps_stdev",
        "qps_min",
        "qps_max",
        "paired_qps_vs_baseline_mean_pct",
        "paired_qps_vs_baseline_median_pct",
        "us_per_query_mean",
        "build_seconds_mean",
        "query_rss_bytes_mean",
        "recall_mean",
    )
    output_rows = []
    for variant in VARIANTS:
        qps = [numeric(rows, block, variant, "qps_mean") for block in range(1, 11)]
        latency = [numeric(rows, block, variant, "us_per_query") for block in range(1, 11)]
        builds = [numeric(rows, block, variant, "build_seconds") for block in range(1, 11)]
        rss = [numeric(rows, block, variant, "query_rss_bytes") for block in range(1, 11)]
        recall = [numeric(rows, block, variant, "recall_mean") for block in range(1, 11)]
        paired = [
            pct(
                numeric(rows, block, variant, "qps_mean"),
                numeric(rows, block, "baseline", "qps_mean"),
            )
            for block in range(1, 11)
        ]
        output_rows.append(
            {
                "variant": variant,
                "trials": len(qps),
                "qps_mean": mean(qps),
                "qps_median": statistics.median(qps),
                "qps_stdev": sample_stdev(qps),
                "qps_min": min(qps),
                "qps_max": max(qps),
                "paired_qps_vs_baseline_mean_pct": mean(paired),
                "paired_qps_vs_baseline_median_pct": statistics.median(paired),
                "us_per_query_mean": mean(latency),
                "build_seconds_mean": mean(builds),
                "query_rss_bytes_mean": mean(rss),
                "recall_mean": mean(recall),
            }
        )

    with (run_dir / "variant_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    return output_rows


def factor_effects(rows):
    effects = {"vector_soa64": [], "hugepage": [], "interaction": []}
    for block in range(1, 11):
        logs = {
            variant: math.log(numeric(rows, block, variant, "qps_mean"))
            for variant in VARIANTS
        }
        effects["vector_soa64"].append(
            ((logs["vector_soa64"] + logs["both"]) - (logs["baseline"] + logs["hugepage"])) / 2.0
        )
        effects["hugepage"].append(
            ((logs["hugepage"] + logs["both"]) - (logs["baseline"] + logs["vector_soa64"])) / 2.0
        )
        effects["interaction"].append(
            logs["both"] - logs["vector_soa64"] - logs["hugepage"] + logs["baseline"]
        )
    return {
        name: {
            "log_effect_mean": mean(values),
            "multiplicative_effect_pct": 100.0 * (math.exp(mean(values)) - 1.0),
            "log_effect_stdev": sample_stdev(values),
        }
        for name, values in effects.items()
    }


def write_markdown(run_dir, summaries, effects):
    lines = [
        "# HNSW factorization summary",
        "",
        "| Variant | Trials | Mean QPS | Median QPS | Paired QPS vs baseline | Mean us/query | Mean recall |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            "| {variant} | {trials} | {qps_mean:.3f} | {qps_median:.3f} | "
            "{paired_qps_vs_baseline_mean_pct:+.3f}% | {us_per_query_mean:.3f} | {recall_mean:.6f} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Balanced 2x2 log-scale effects",
            "",
            "| Effect | Multiplicative QPS effect | Mean log effect | SD across blocks |",
            "|---|---:|---:|---:|",
        ]
    )
    for name in ("vector_soa64", "hugepage", "interaction"):
        row = effects[name]
        lines.append(
            f"| {name} | {row['multiplicative_effect_pct']:+.3f}% | "
            f"{row['log_effect_mean']:+.6f} | {row['log_effect_stdev']:.6f} |"
        )
    lines.extend(
        [
            "",
            "Effects are contrasts over all four cells within each execution block. Inspect raw trial ranges and paired results before drawing conclusions.",
            "",
        ]
    )
    (run_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: summarize_factorization.py RUN_DIR")
    run_dir = Path(sys.argv[1]).resolve()
    if not run_dir.is_dir():
        raise SystemExit(f"not a run directory: {run_dir}")
    rows = read_results(run_dir)
    summaries = write_variant_summary(run_dir, rows)
    effects = factor_effects(rows)
    write_markdown(run_dir, summaries, effects)
    print(run_dir / "summary.md")


if __name__ == "__main__":
    main()

