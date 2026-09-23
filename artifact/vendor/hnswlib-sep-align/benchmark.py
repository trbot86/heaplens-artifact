#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def parse_csv_ints(value):
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_defines(value):
    defines = []
    for item in value.replace(",", " ").split():
        item = item.strip()
        if not item:
            continue
        if item.startswith("-D"):
            item = item[2:]
        defines.append(item)
    return defines


def slugify(value):
    slug = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    slug = re.sub(r"^[-_]+", "", slug)
    slug = re.sub(r"_+$", "", slug)
    return slug or "custom"


def variant_from_token(token):
    if token in ("baseline", "none"):
        return "baseline", ""
    slug = slugify(token)
    if token.isdigit():
        return "variant_{}".format(token), "HNSWLIB_BENCH_VARIANT={}".format(token)
    if (
        token.startswith("-D") or
        "," in token or
        "=" in token or
        re.match(r"^[A-Z_][A-Z0-9_]*$", token)
    ):
        return slug, token
    variant_macro = slug.upper().replace(".", "_").replace("-", "_")
    return slug, "HNSWLIB_BENCH_VARIANT_{}".format(variant_macro)


def parse_args(argv=None):
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and (not raw_args[0].startswith("--") or raw_args[0].startswith("-D")):
        raw_args[0] = "--variant-token={}".format(raw_args[0])

    parser = argparse.ArgumentParser()
    parser.add_argument("--variant-token", default="")
    parser.add_argument("--variant-defines", default="")
    parser.add_argument("--variant-label", default="baseline")
    parser.add_argument("--dims", default="16,128")
    parser.add_argument("--threads", default="1")
    parser.add_argument("--elements", type=int, default=20000)
    parser.add_argument("--queries", type=int, default=2000)
    parser.add_argument("--m", type=int, default=16)
    parser.add_argument("--ef-construction", type=int, default=60)
    parser.add_argument("--ef", type=int, default=15)
    parser.add_argument("--k", type=int, default=1)
    parser.add_argument("--build-threads", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=0)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--query-mode", choices=("first", "indexed"), default="first")
    parser.add_argument("--numa-node", default="")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--delete-every", type=int, default=0)
    parser.add_argument("--output", default="")
    parser.add_argument("--no-native", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--repetition", type=int, default=1)
    args = parser.parse_args(raw_args)
    if args.variant_token:
        label, defines = variant_from_token(args.variant_token)
        if args.variant_label == "baseline":
            args.variant_label = label
        if not args.variant_defines:
            args.variant_defines = defines
    return args


def max_rss_kb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def current_rss_bytes():
    try:
        with open("/proc/self/statm") as fh:
            fields = fh.read().split()
        return int(fields[1]) * os.sysconf("SC_PAGESIZE")
    except (OSError, IndexError, ValueError):
        return 0


def splitmix64(value):
    value = (value + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return (value ^ (value >> 31)) & 0xFFFFFFFFFFFFFFFF


def indexed_query_ids(count, elements, seed):
    query_seed = seed ^ 0x123456789ABCDEF0
    ids = []
    step = 0xBF58476D1CE4E5B9
    for i in range(count):
        ids.append(splitmix64((query_seed + i * step) & 0xFFFFFFFFFFFFFFFF) % elements)
    return ids


def run_query(index, qdata, query_ids, k, threads, np):
    t0 = time.perf_counter()
    labels, _ = index.knn_query(qdata, k=k, num_threads=threads)
    elapsed = time.perf_counter() - t0
    expected = np.asarray(query_ids, dtype=labels.dtype)
    recall = float(np.mean(np.any(labels == expected[:, None], axis=1)))
    return elapsed, recall


def run_probe(args):
    import hnswlib
    import numpy as np

    rng = np.random.default_rng(args.seed)
    data = rng.random((args.elements, args.dims), dtype=np.float32)
    ids = np.arange(args.elements, dtype=np.uint64)

    index = hnswlib.Index(space="l2", dim=args.dims)
    index.init_index(
        max_elements=args.elements,
        M=args.m,
        ef_construction=args.ef_construction,
        random_seed=args.seed,
        allow_replace_deleted=bool(args.delete_every),
    )
    index.set_num_threads(args.build_threads)

    t0 = time.perf_counter()
    index.add_items(data, ids, num_threads=args.build_threads)
    build_seconds = time.perf_counter() - t0
    build_rss_bytes = current_rss_bytes()

    deleted = 0
    if args.delete_every > 0:
        for label in range(0, args.elements, args.delete_every):
            index.mark_deleted(int(label))
            deleted += 1

    index.set_ef(args.ef)
    index.set_num_threads(args.threads)

    if args.query_mode == "indexed":
        candidate_count = min(args.queries, args.elements - deleted)
        query_ids = indexed_query_ids(candidate_count, args.elements, args.seed)
        if args.delete_every > 0:
            query_ids = [i for i in query_ids if i % args.delete_every != 0]
    elif args.delete_every > 0:
        query_ids = [i for i in range(args.elements) if i % args.delete_every != 0][:args.queries]
    else:
        query_ids = list(range(min(args.queries, args.elements)))
    qdata = data[query_ids]

    warmup_seconds = 0.0
    warmup_recall = 0.0
    if args.warmup > 0:
        warmup_ids = np.resize(np.asarray(query_ids, dtype=np.int64), args.warmup)
        warmup_data = data[warmup_ids]
        warmup_seconds, warmup_recall = run_query(
            index, warmup_data, warmup_ids, args.k, args.threads, np)

    iteration_seconds = []
    recall_values = []
    for _ in range(args.iterations):
        elapsed, recall = run_query(index, qdata, query_ids, args.k, args.threads, np)
        iteration_seconds.append(elapsed)
        recall_values.append(recall)

    query_seconds = sum(iteration_seconds)
    timed_queries = int(len(query_ids) * args.iterations)
    result = {
        "variant": args.variant_label,
        "defines": args.variant_defines,
        "repetition": args.repetition,
        "dim": args.dims,
        "elements": args.elements,
        "queries": int(len(query_ids)),
        "timed_queries": timed_queries,
        "m": args.m,
        "ef_construction": args.ef_construction,
        "ef": args.ef,
        "k": args.k,
        "threads": args.threads,
        "build_threads": args.build_threads,
        "warmup": args.warmup,
        "warmup_seconds": warmup_seconds,
        "warmup_recall": warmup_recall,
        "iterations": args.iterations,
        "query_mode": args.query_mode,
        "deleted": deleted,
        "build_seconds": build_seconds,
        "build_rss_bytes": int(build_rss_bytes),
        "query_seconds": query_seconds,
        "query_iteration_mean_seconds": statistics.mean(iteration_seconds),
        "query_iteration_median_seconds": statistics.median(iteration_seconds),
        "query_iteration_min_seconds": min(iteration_seconds),
        "qps_mean": timed_queries / query_seconds if query_seconds else 0.0,
        "us_per_query": 1000000.0 * query_seconds / timed_queries if timed_queries else 0.0,
        "recall_mean": statistics.mean(recall_values),
        "index_file_size": int(index.index_file_size()),
        "query_rss_bytes": int(current_rss_bytes()),
        "max_rss_kb": int(max_rss_kb()),
    }
    print(json.dumps(result, sort_keys=True))


def run_command(cmd, env):
    return subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def build_variant(label, defines, args):
    env = os.environ.copy()
    env["HNSWLIB_BENCH_CXX_DEFINES"] = ",".join(defines)
    if args.no_native:
        env["HNSWLIB_NO_NATIVE"] = "1"
    if args.skip_build:
        return 0.0
    t0 = time.perf_counter()
    result = run_command(
        [sys.executable, "setup.py", "build_ext", "--inplace", "--force"],
        env,
    )
    elapsed = time.perf_counter() - t0
    if result.returncode != 0:
        raise RuntimeError(
            "build failed for {} with defines {}\n{}".format(
                label,
                ",".join(defines),
                result.stdout,
            )
        )
    return elapsed


def run_probe_subprocess(label, defines, dim, threads, repetition, args):
    cmd = [
        sys.executable,
        "benchmark.py",
        "--probe",
        "--variant-label={}".format(label),
        "--variant-defines={}".format(",".join(defines)),
        "--dims", str(dim),
        "--elements", str(args.elements),
        "--queries", str(args.queries),
        "--m", str(args.m),
        "--ef-construction", str(args.ef_construction),
        "--ef", str(args.ef),
        "--k", str(args.k),
        "--threads", str(threads),
        "--build-threads", str(args.build_threads),
        "--warmup", str(args.warmup),
        "--iterations", str(args.iterations),
        "--query-mode", args.query_mode,
        "--repetition", str(repetition),
        "--seed", str(args.seed),
        "--delete-every", str(args.delete_every),
    ]
    if args.numa_node:
        cmd = [
            "numactl",
            "--cpunodebind={}".format(args.numa_node),
            "--membind={}".format(args.numa_node),
        ] + cmd
    result = run_command(cmd, os.environ.copy())
    if result.returncode != 0:
        raise RuntimeError(
            "probe failed for {} dim={} threads={}\n{}".format(
                label,
                dim,
                threads,
                result.stdout,
            )
        )
    return json.loads(result.stdout.strip().splitlines()[-1])


def run_sequence(args):
    dims = parse_csv_ints(args.dims)
    thread_counts = parse_csv_ints(args.threads)
    label = args.variant_label
    defines = parse_defines(args.variant_defines)
    output = Path(args.output) if args.output else ROOT / "benchmark_results.csv"

    rows = []
    print("building {} [{}]".format(label, ",".join(defines)), flush=True)
    build_seconds = build_variant(label, defines, args)
    for dim in dims:
        for threads in thread_counts:
            for repetition in range(1, args.repeats + 1):
                print(
                    "running {} dim={} threads={} repetition={}/{}".format(
                        label, dim, threads, repetition, args.repeats),
                    flush=True)
                row = run_probe_subprocess(label, defines, dim, threads, repetition, args)
                row["variant_build_seconds"] = build_seconds
                rows.append(row)

    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with output.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("wrote {}".format(output))


def main():
    args = parse_args()
    if args.probe:
        if "," in args.dims:
            raise RuntimeError("--probe expects a single --dims value")
        args.dims = int(args.dims)
        args.threads = int(args.threads)
        run_probe(args)
    else:
        run_sequence(args)


if __name__ == "__main__":
    main()
