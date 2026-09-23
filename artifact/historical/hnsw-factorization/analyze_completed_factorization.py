#!/usr/bin/env python3
import csv
import glob
import os
import statistics
import sys


run_dir = sys.argv[1]
rows = {}
for path in glob.glob(os.path.join(run_dir, "block??_*.csv")):
    name = os.path.basename(path)
    block = int(name[5:7])
    label = name[8:-4]
    with open(path, newline="") as stream:
        rows[(block, label)] = next(csv.DictReader(stream))

print(
    "block,baseline_qps,vector_qps,huge_qps,both_qps,"
    "both_vs_baseline_pct,both_vs_vector_pct,huge_vs_baseline_pct,"
    "both_minus_baseline_recall"
)
total_effect = []
vector_hugepage_effect = []
packed_hugepage_effect = []
recall_delta = []
for block in range(1, 11):
    qps = {
        label: float(rows[(block, label)]["qps_mean"])
        for label in ("baseline", "vector_soa64", "hugepage", "both")
    }
    recall = (
        float(rows[(block, "both")]["recall_mean"])
        - float(rows[(block, "baseline")]["recall_mean"])
    )
    total = (qps["both"] / qps["baseline"] - 1.0) * 100.0
    vector_hugepage = (qps["both"] / qps["vector_soa64"] - 1.0) * 100.0
    packed_hugepage = (qps["hugepage"] / qps["baseline"] - 1.0) * 100.0
    total_effect.append(total)
    vector_hugepage_effect.append(vector_hugepage)
    packed_hugepage_effect.append(packed_hugepage)
    recall_delta.append(recall)
    print(
        f"{block},{qps['baseline']:.3f},{qps['vector_soa64']:.3f},"
        f"{qps['hugepage']:.3f},{qps['both']:.3f},{total:+.3f},"
        f"{vector_hugepage:+.3f},{packed_hugepage:+.3f},{recall:+.6f}"
    )

print(
    f"mean both_vs_baseline={statistics.mean(total_effect):+.3f}% "
    f"sd={statistics.stdev(total_effect):.3f}"
)
print(
    f"mean both_vs_vector={statistics.mean(vector_hugepage_effect):+.3f}% "
    f"sd={statistics.stdev(vector_hugepage_effect):.3f}"
)
print(
    f"mean huge_vs_baseline={statistics.mean(packed_hugepage_effect):+.3f}% "
    f"sd={statistics.stdev(packed_hugepage_effect):.3f}"
)
print(
    f"mean recall delta both-baseline={statistics.mean(recall_delta):+.6f} "
    f"sd={statistics.stdev(recall_delta):.6f} "
    f"min={min(recall_delta):+.6f} max={max(recall_delta):+.6f}"
)
