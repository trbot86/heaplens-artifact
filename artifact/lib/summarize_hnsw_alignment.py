#!/usr/bin/env python3
import csv
import math
import statistics
import sys
from pathlib import Path


LABELS = ("packed", "separated_unaligned32", "separated_aligned64")
DISPLAY = {
    "packed": "P: packed",
    "separated_unaligned32": "S-U: separated, +32 B",
    "separated_aligned64": "S-A: separated, 64 B aligned",
}


def read_one(path: Path) -> dict[str, str]:
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 1:
        raise SystemExit(f"expected one row in {path}, found {len(rows)}")
    return rows[0]


def pct(log_effect: float) -> float:
    return math.expm1(log_effect) * 100.0


run_dir = Path(sys.argv[1]).resolve()
rows: dict[tuple[int, str], dict[str, str]] = {}
for path in sorted(run_dir.glob("block??_*.csv")):
    block = int(path.name[5:7])
    label = path.stem[8:]
    rows[(block, label)] = read_one(path)

expected = {(block, label) for block in range(1, 7) for label in LABELS}
if set(rows) != expected:
    missing = sorted(expected - set(rows))
    extra = sorted(set(rows) - expected)
    raise SystemExit(f"cell mismatch: missing={missing} extra={extra}")

variant_rows = []
for label in LABELS:
    qps = [float(rows[(block, label)]["qps_mean"]) for block in range(1, 7)]
    build = [float(rows[(block, label)]["build_seconds"]) for block in range(1, 7)]
    recall = [float(rows[(block, label)]["recall_mean"]) for block in range(1, 7)]
    us = [float(rows[(block, label)]["us_per_query"]) for block in range(1, 7)]
    variant_rows.append(
        {
            "variant": label,
            "trials": len(qps),
            "qps_mean": statistics.mean(qps),
            "qps_median": statistics.median(qps),
            "qps_stdev": statistics.stdev(qps),
            "qps_min": min(qps),
            "qps_max": max(qps),
            "build_seconds_mean": statistics.mean(build),
            "recall_mean": statistics.mean(recall),
            "us_per_query_mean": statistics.mean(us),
        }
    )

with (run_dir / "variant_summary.csv").open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(variant_rows[0]))
    writer.writeheader()
    writer.writerows(variant_rows)

block_effects = []
for block in range(1, 7):
    qps = {label: float(rows[(block, label)]["qps_mean"]) for label in LABELS}
    recall = {label: float(rows[(block, label)]["recall_mean"]) for label in LABELS}
    separation_log = math.log(qps["separated_unaligned32"]) - math.log(qps["packed"])
    alignment_log = math.log(qps["separated_aligned64"]) - math.log(qps["separated_unaligned32"])
    total_log = math.log(qps["separated_aligned64"]) - math.log(qps["packed"])
    if not math.isclose(separation_log + alignment_log, total_log, rel_tol=0.0, abs_tol=1e-12):
        raise SystemExit(f"log decomposition failed in block {block}")
    block_effects.append(
        {
            "block": block,
            "packed_qps": qps["packed"],
            "separated_unaligned32_qps": qps["separated_unaligned32"],
            "separated_aligned64_qps": qps["separated_aligned64"],
            "separation_log_effect": separation_log,
            "alignment_log_effect": alignment_log,
            "total_log_effect": total_log,
            "separation_pct": pct(separation_log),
            "alignment_pct": pct(alignment_log),
            "total_pct": pct(total_log),
            "unaligned_minus_packed_recall": recall["separated_unaligned32"] - recall["packed"],
            "aligned_minus_unaligned_recall": recall["separated_aligned64"] - recall["separated_unaligned32"],
            "aligned_minus_packed_recall": recall["separated_aligned64"] - recall["packed"],
        }
    )

with (run_dir / "block_effects.csv").open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(block_effects[0]))
    writer.writeheader()
    writer.writerows(block_effects)

effect_specs = (
    ("Separation under controlled +32 B offset", "separation_log_effect"),
    ("64 B alignment conditional on separation", "alignment_log_effect"),
    ("Separated and aligned versus packed", "total_log_effect"),
)
effect_summary = []
for name, field in effect_specs:
    values = [float(row[field]) for row in block_effects]
    mean_log = statistics.mean(values)
    sd_log = statistics.stdev(values)
    margin = 2.571 * sd_log / math.sqrt(len(values))
    effect_summary.append(
        {
            "name": name,
            "field": field,
            "mean_log": mean_log,
            "sd_log": sd_log,
            "effect_pct": pct(mean_log),
            "ci_low_pct": pct(mean_log - margin),
            "ci_high_pct": pct(mean_log + margin),
            "positive_blocks": sum(value > 0 for value in values),
            "negative_blocks": sum(value < 0 for value in values),
        }
    )

separation_mean = effect_summary[0]["mean_log"]
alignment_mean = effect_summary[1]["mean_log"]
total_mean = effect_summary[2]["mean_log"]
stable_shares = (
    total_mean != 0
    and separation_mean * total_mean > 0
    and alignment_mean * total_mean > 0
    and effect_summary[0]["positive_blocks"] in (0, 6)
    and effect_summary[1]["positive_blocks"] in (0, 6)
)

lines = [
    "# HNSWLib separation/alignment factorization",
    "",
    "Six blocks contain all six execution orders exactly once. Huge-page advice is disabled in all cells.",
    "",
    "## Variant summary",
    "",
    "| Variant | Trials | Mean QPS | SD QPS | Mean us/query | Mean build s | Mean recall |",
    "|---|---:|---:|---:|---:|---:|---:|",
]
for row in variant_rows:
    lines.append(
        f"| {DISPLAY[row['variant']]} | {row['trials']} | {row['qps_mean']:.3f} | "
        f"{row['qps_stdev']:.3f} | {row['us_per_query_mean']:.3f} | "
        f"{row['build_seconds_mean']:.3f} | {row['recall_mean']:.6f} |"
    )

lines.extend(
    [
        "",
        "## Paired log-QPS decomposition",
        "",
        "| Contrast | Multiplicative effect | Approx. 95% block CI | Mean log effect | SD log effect | Signs |",
        "|---|---:|---:|---:|---:|---:|",
    ]
)
for row in effect_summary:
    lines.append(
        f"| {row['name']} | {row['effect_pct']:+.3f}% | "
        f"[{row['ci_low_pct']:+.3f}%, {row['ci_high_pct']:+.3f}%] | "
        f"{row['mean_log']:+.6f} | {row['sd_log']:.6f} | "
        f"{row['positive_blocks']}+/{row['negative_blocks']}- |"
    )

lines.extend(
    [
        "",
        "For every block, `log(S-A/P) = log(S-U/P) + log(S-A/S-U)` exactly up to floating-point rounding.",
    ]
)
if stable_shares:
    lines.extend(
        [
            "",
            "Because both component effects have the same sign as the total effect in every block, conditional log-effect shares are:",
            "",
            f"- Separation under +32 B offset: {100.0 * separation_mean / total_mean:.1f}%",
            f"- 64 B alignment conditional on separation: {100.0 * alignment_mean / total_mean:.1f}%",
        ]
    )
else:
    lines.extend(
        [
            "",
            "Component signs are not stable enough to report proportional attribution; report the paired effects directly.",
        ]
    )

lines.extend(
    [
        "",
        "## Per-block effects",
        "",
        "| Block | S-U vs P | S-A vs S-U | S-A vs P |",
        "|---:|---:|---:|---:|",
    ]
)
for row in block_effects:
    lines.append(
        f"| {row['block']} | {row['separation_pct']:+.3f}% | "
        f"{row['alignment_pct']:+.3f}% | {row['total_pct']:+.3f}% |"
    )

lines.extend(
    [
        "",
        "Interpret S-U versus P as the practical separation transformation with a controlled non-64-byte-aligned slab, not a theoretically pure separation factor: packed vectors naturally occupy a distribution of cache-line offsets.",
        "",
    ]
)
(run_dir / "summary.md").write_text("\n".join(lines))
print(run_dir / "summary.md")
