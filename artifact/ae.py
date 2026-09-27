#!/usr/bin/env python3
"""ATC artifact entry point. Only explicit paper profiles run large experiments."""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import statistics
import subprocess
import sys
import time
from lib.perfstat_campaign import schedule
from lib import hnsw_campaign
from lib import rocksdb_memoryonly, rocksdb_hashskiplist

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifact"
VENDOR = ART / "vendor"
IGNORE = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "*.o", "*.so", "build", ".cache")
EXPERIMENTS = ["ascylib_efrb", "ascylib_dvy", "ascylib_hj", "tpcc_bcco", "tpcc_efrb", "rocksdb_hsl",
          "ascylib_efrb_bench", "ascylib_dvy_bench", "ascylib_hj_bench", "tpcc_bcco_bench", "tpcc_efrb_bench"]

def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")

def run(cmd, *, cwd=ROOT, log=None, env=None, timeout=None):
    cmd = [str(x) for x in cmd]
    print("+", " ".join(cmd), flush=True)
    if log:
        with Path(log).open("a") as f:
            f.write("COMMAND: " + repr(cmd) + "\n"); f.flush()
            proc = subprocess.run(cmd, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
        if proc.returncode:
            raise RuntimeError(f"Exit {proc.returncode}; see {log}")
    else:
        subprocess.run(cmd, cwd=cwd, env=env, check=True, timeout=timeout)

def new_output(args):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S-%fZ")
    path = Path(args.out).resolve() if args.out else ART / "results" / f"{args.command}-{stamp}"
    path.mkdir(parents=True, exist_ok=False)
    save(path / "environment.json", {"created_utc": stamp, "platform": platform.platform(),
         "python": sys.version, "arguments": vars(args), "affinity": sorted(os.sched_getaffinity(0)),
         "note": "Smoke runs are functionality checks, not performance evidence."})
    for name, cmd in (("cpu.txt", ["lscpu"]), ("numa.txt", ["numactl", "--hardware"]),
                      ("compiler.txt", ["gcc", "--version"])):
        run(cmd, log=path / name)
    return path

def compare(values):
    baseline = statistics.mean(values["baseline"])
    return {"variants": {name: {"runs": len(xs), "mean": statistics.mean(xs),
             "stdev": statistics.stdev(xs) if len(xs) > 1 else None,
             "change_percent_vs_baseline": 100 * (statistics.mean(xs) / baseline - 1)}
             for name, xs in values.items()}, "statistic": "ratio of arithmetic means; not mean of paired ratios"}

def history():
    values = {}
    for variant, tag in (("baseline", "A0"), ("B1C1_64", "B1C1_64")):
        files = sorted((ART / "historical/valkey/benchmark_runs").glob(f"*_{tag}_rep*/summary.json"))
        if len(files) != 10:
            raise RuntimeError(f"Expected 10 Valkey records for {tag}, got {len(files)}")
        values[variant] = [json.loads(p.read_text())["results"]["ops_per_sec"] for p in files]
    print("SAVED HISTORICAL VALKEY RESULTS (not a new experiment)")
    print(json.dumps(compare(values), indent=2))
    values = {}
    for variant, name in (("baseline", "rerun_baseline_768t24_r10.csv"), ("vector_huge", "rerun_vector_huge_768t24_r10.csv")):
        with (ART / "historical/hnswlib/results" / name).open() as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 10:
            raise RuntimeError(f"Expected 10 HNSW records in {name}, got {len(rows)}")
        values[variant] = [float(row["qps_mean"]) for row in rows]
    print("SAVED HISTORICAL HNSWLIB RESULTS (not a new experiment)")
    print(json.dumps(compare(values), indent=2))
    print("SAVED HNSWLIB LAYOUT / HUGE-PAGE FACTORIZATION")
    run([sys.executable, ART / "historical/hnsw-factorization/analyze_completed_factorization.py", ART / "historical/hnsw-factorization"])

def doctor():
    missing = [tool for tool in ("clang-14", "clang-tidy-14", "clang-apply-replacements-14", "cmake", "bear",
               "sqlite3", "node", "npm", "numactl", "patch", "gcc", "g++", "make") if not shutil.which(tool)]
    run([sys.executable, "-c", "import flask,numpy,pandas,sklearn,pybind11,yaml; print('Python imports OK')"])
    with __import__("sqlite3").connect(f"file:{ART / 'data/valkey/allocs.sqlite'}?mode=ro", uri=True) as db:
        assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    print("Missing tools:", missing or "none")
    print("perf is optional; PMU permission/support is NOT assumed. No sysctls are changed.")
    if missing: raise RuntimeError("Missing dependencies; use artifact/Dockerfile")

def export(out):
    run([sys.executable, ROOT / "sifter_vis_d3/server/export_page_snapshots.py",
         ART / "data/valkey/allocs.sqlite", out / "export"], log=out / "export.log")
    files = list((out / "export/compact").glob("*.txt"))
    if not files or not (out / "export/heaplens_analysis.txt").is_file():
        raise RuntimeError("Exporter produced incomplete output")
    print(f"Export OK: {len(files)} compact files; {out / 'export'}")

def hnsw(args, out):
    paper = args.profile == "paper"
    repeats = args.reps or (10 if paper else 1)
    cells = {"baseline":"", "vector_huge":"HNSWLIB_LAYOUT_VECTOR_SOA64=1,HNSWLIB_LAYOUT_MADVISE_HUGEPAGE=1"}
    source = VENDOR / ("hnswlib" if args.hnsw_source == "original" else "hnswlib-corrected")
    if args.trial_order == "blocked":
        execution = [(label, block+1) for label,block in schedule(list(cells), repeats, "blocked")]
    else:
        execution = [(label,block) for block in range(1,repeats+1)
                     for label in (list(cells) if block%2 else list(cells)[::-1])]
    values = hnsw_campaign.execute(args,out,source,cells,execution,sys.modules[__name__])
    dims = hnsw_campaign.dimensions(args)
    summary = ({"by_dimension":{str(dim):compare(values[dim]) for dim in dims}}
               if len(dims)>1 else compare(values))
    summary["dimensions"] = dims
    summary["profile"] = args.profile
    summary["source"] = source.name
    summary["scope"] = "Huge-page advice is not proof of huge-page backing; source and exact workload are in protocol.json."
    save(out / "summary.json", summary)
    print(json.dumps(summary, indent=2))

def node_cpus(node, needed, requested=None):
    text = subprocess.check_output(["lscpu", "-p=CPU,NODE,CORE,ONLINE"], text=True)
    available = {}
    affinity = os.sched_getaffinity(0)
    for line in text.splitlines():
        if not line or line.startswith("#"): continue
        cpu, numa, core, online = line.split(",")
        if numa == str(node) and online == "Y" and int(cpu) in affinity:
            available[int(cpu)] = core
    if requested is not None:
        result = []
        for part in requested.split(","):
            if not re.fullmatch(r"[0-9]+(?:-[0-9]+)?", part):
                raise ValueError("--cpus requires CPU IDs/ranges, such as 0-7 or 0,2,4,6")
            bounds = list(map(int, part.split("-")))
            start, end = bounds[0], bounds[-1]
            if start > end or end > max(available, default=-1):
                raise ValueError("CPU range is outside the selected node's available CPUs")
            result.extend(range(start, end + 1))
        if len(result) != needed or len(set(result)) != needed:
            raise ValueError("--cpus must contain exactly --threads distinct CPU IDs")
        if any(cpu not in available for cpu in result):
            raise ValueError("Every selected CPU must be online, allowed, and on --server-node")
        if len({available[cpu] for cpu in result}) != needed:
            raise ValueError("Select one hardware thread per physical core, not SMT siblings")
        return result
    result, seen = [], set()
    for cpu, core in available.items():
        if core not in seen:
            result.append(cpu); seen.add(core)
    if len(result) < needed: raise RuntimeError(f"NUMA node {node}: need {needed} available physical cores, found {len(result)}; use smoke on smaller hosts")
    return result[:needed]

def memory_option(args, default="bind"):
    return "membind" if (args.memory_policy or default) == "bind" else "interleave"

def build_valkey(work, jobs, log):
    # Generate the omitted configure; keep Valkey's original allocator options.
    if not (work / "deps/jemalloc/configure").is_file():
        run(["autoconf"], cwd=work / "deps/jemalloc", log=log)
    run(["make", f"-j{jobs}", "MALLOC=jemalloc", "BUILD_TLS=no", "BUILD_RDMA=no", "BUILD_LUA=no", "USE_SYSTEMD=no"],
        cwd=work, log=log)

def valkey(args, out):
    paper = args.profile == "paper"
    threads, keys, seconds = (24, 4000000, 30) if paper else (2, 10000, 3)
    reps = args.reps or (10 if paper else 1)
    prefixes = [[], []]
    placement = {"pinning": False}
    if paper:
        if args.server_node == args.client_node: raise RuntimeError("Paper profile requires separate NUMA nodes")
        cpus = [node_cpus(args.server_node, threads), node_cpus(args.client_node, threads)]
        prefixes = [["numactl", "--physcpubind=" + ",".join(map(str, ids)), f"--membind={node}"]
                    for ids, node in zip(cpus, [args.server_node, args.client_node])]
        placement = {"pinning": True, "server_cpus": cpus[0], "client_cpus": cpus[1],
                     "server_node": args.server_node, "client_node": args.client_node}
    config = {"profile": args.profile, "threads": threads, "keys": keys, "seconds": seconds, "repetitions": reps,
              "allocator": "bundled jemalloc", "set_get_ratio": "1:4", "clients_per_thread": 4,
              "pipeline": 16, "data_size": 128, "placement": placement,
              "order": "alternating AB/BA; fresh server and preload each trial"}
    save(out / "config.json", config)
    memtier = out / "memtier"
    shutil.copytree(VENDOR / "memtier", memtier, ignore=IGNORE)
    for cmd in (["autoreconf", "-ivf"], ["./configure", "--disable-tls"], ["make", f"-j{args.jobs}"]):
        run(cmd, cwd=memtier, log=out / "memtier-build.log")
    for variant in ("baseline", "B1C1_64"):
        work = out / variant
        shutil.copytree(VENDOR / "valkey", work, ignore=IGNORE)
        if variant != "baseline":
            run(["patch", "--batch", "-p1", "-i", ART / "patches/valkey-B1C1_64.patch"], cwd=work, log=out / "patch.log")
        build_valkey(work, args.jobs, out / f"{variant}-build.log")
    values = {"baseline": [], "B1C1_64": []}
    for rep in range(reps):
        variants = ["baseline", "B1C1_64"] if rep % 2 == 0 else ["B1C1_64", "baseline"]
        for variant in variants:
            trial = out / f"{variant}-rep{rep + 1}"
            trial.mkdir()
            # Choose an unused loopback port. Never stop an existing service.
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
            server_cmd = prefixes[0] + [str(out / variant / "src/valkey-server"), "--bind", "127.0.0.1", "--port", str(port),
                         "--protected-mode", "yes", "--save", "", "--appendonly", "no", "--daemonize", "no", "--dir", str(trial),
                         "--io-threads", str(threads), "--io-threads-always-active", "yes"]
            save(trial / "server-command.json", server_cmd)
            with (trial / "server.log").open("w") as log:
                proc = subprocess.Popen(server_cmd, stdout=log, stderr=subprocess.STDOUT)
                try:
                    for attempt in range(200):
                        if proc.poll() is not None: raise RuntimeError(f"Server exited; see {trial / 'server.log'}")
                        try:
                            with socket.create_connection(("127.0.0.1", port), timeout=.2) as sock:
                                sock.sendall(b"PING\r\n")
                                if sock.recv(100).startswith(b"+PONG"): break
                        except OSError: pass
                        time.sleep(.1)
                    else: raise RuntimeError("Server did not become ready")
                    common = prefixes[1] + [str(memtier / "memtier_benchmark"), "--server=127.0.0.1", f"--port={port}", "--protocol=redis",
                        f"--threads={threads}", "--clients=4", "--pipeline=16", "--key-prefix=heaplens:", "--key-minimum=1",
                        f"--key-maximum={keys}", "--data-size=128", "--distinct-client-seed", "--hide-histogram"]
                    run(common + ["--ratio=1:0", "--key-pattern=P:P", "--requests=allkeys", f"--json-out-file={trial / 'preload.json'}"],
                        log=trial / "preload.log", timeout=1800)
                    run(common + ["--ratio=1:4", "--key-pattern=R:R", f"--test-time={seconds}", f"--json-out-file={trial / 'benchmark.json'}"],
                        log=trial / "benchmark.log", timeout=seconds + 120)
                    totals = json.loads((trial / "benchmark.json").read_text())["ALL STATS"]["Totals"]
                    if totals["Connection Errors"] != 0 or totals["Misses/sec"] != 0:
                        raise RuntimeError(f"Connection errors or cache misses in {trial}; check preload/workload")
                    values[variant].append(float(totals["Ops/sec"]))
                    save(trial / "summary.json", {"config": config, "results": totals})
                finally:
                    # Signal only the process started above, never a process found by port/name.
                    if proc.poll() is None:
                        proc.terminate()
                        try: proc.wait(timeout=10)
                        except subprocess.TimeoutExpired: proc.kill(); proc.wait()
    summary = compare(values); summary["profile"] = args.profile
    save(out / "summary.json", summary)
    print(json.dumps(summary, indent=2))

def gui():
    dest = ROOT / "sifter_vis_d3/valkey-artifact.sqlite"
    source = ART / "data/valkey/allocs.sqlite"
    if dest.exists() and hashlib.sha256(dest.read_bytes()).digest() != hashlib.sha256(source.read_bytes()).digest():
        raise RuntimeError(f"Refusing to replace {dest}")
    if not dest.exists(): shutil.copy2(source, dest)
    efrb = ROOT / "sifter_vis_d3/efrb-smoke.sqlite"
    if not efrb.exists(): shutil.copy2(ART / "data/efrb/allocs.sqlite", efrb)
    backend = ROOT / "sifter_vis_d3/server"
    (backend / "saved_state").mkdir(exist_ok=True)
    frontend = ROOT / "sifter_vis_d3/sifter"
    if not (frontend / "node_modules").exists():
        if Path("/opt/heaplens-ui/node_modules").exists(): (frontend / "node_modules").symlink_to("/opt/heaplens-ui/node_modules")
        else: run(["npm", "ci", "--no-audit", "--no-fund"], cwd=frontend)
    procs = []
    try:
        procs.append(subprocess.Popen([sys.executable, "-m", "flask", "--app", "server", "run", "--host=0.0.0.0"], cwd=backend))
        procs.append(subprocess.Popen(["npm", "run", "dev", "--", "--hostname", "0.0.0.0"], cwd=frontend))
        print("Open http://localhost:3000 and select valkey-artifact.sqlite. Ctrl-C stops both services.", flush=True)
        while all(p.poll() is None for p in procs): time.sleep(1)
        raise RuntimeError("A GUI service exited")
    except KeyboardInterrupt: pass
    finally:
        for p in procs:
            if p.poll() is None: p.terminate()
        for p in procs:
            try: p.wait(timeout=10)
            except subprocess.TimeoutExpired: p.kill(); p.wait()

def rocksdb(args, out):
    paper = args.profile == "paper"
    memory_only = args.memtable == "skip_list"
    threads, keys, duration = ((20, 10000000, 60) if memory_only else (96, 10000000, 10)) if paper else (2, 10000, 2)
    threads = args.threads or threads
    reps = args.reps or (10 if paper else 1)
    placement = []
    if paper or args.cpus or args.memory_policy or (not memory_only and args.rocks_nodes):
        if memory_only:
            ids = node_cpus(args.server_node, threads, args.cpus)
            placement = ["numactl", "--physcpubind=" + ",".join(map(str, ids)), f"--{memory_option(args)}={args.server_node}"]
        else:
            nodes = args.rocks_nodes or [0, 1]
            ids = rocksdb_hashskiplist.cpus(nodes, threads, args.cpus)
            policy = "membind" if args.memory_policy == "bind" else "interleave"
            placement = ["numactl", "--physcpubind=" + ",".join(map(str, ids)), f"--{policy}=" + ",".join(map(str, nodes))]
    flags = ["ALIGN_TALL_NODE=3", "SEG_TALL_NODE=3"] if memory_only else ["REORDER_FIELDS=1"]
    allocator = VENDOR / "heaplens-allocators/libjemalloc-heaplens.so"
    env = rocksdb_memoryonly.environment(allocator)
    available = rocksdb_memoryonly.check_memory() if paper and memory_only else None
    options_file = out / "rocksdb-options.ini"
    options_hash = None
    if memory_only:
        options_hash = rocksdb_memoryonly.write_options(
            ART / "config/rocksdb-memoryonly" / f"{args.memtable}.ini", options_file, threads, args.rocks_key_size)
    persistence = "memory-only" if memory_only else "flushing and compaction enabled; WAL disabled"
    benchmarks = "filluniquerandom,readwhilewriting" if memory_only else "filluniquerandom,waitforcompaction,readwhilewriting"
    workload_options = [f"--options_file={options_file}"] if memory_only else rocksdb_hashskiplist.workload_args(threads)
    save(out / "protocol.json", {"persistence": persistence, "threads": threads, "keys": keys,
         "key_size": args.rocks_key_size, "value_size": args.rocks_value_size, "duration_seconds": duration,
         "write_buffer_bytes": rocksdb_memoryonly.WRITE_BUFFER_BYTES if memory_only else rocksdb_hashskiplist.WRITE_BUFFER_BYTES,
         "benchmarks": benchmarks, "workload_options": workload_options, "placement": placement,
         "allocator": str(allocator), "allocator_sha256": rocksdb_memoryonly.sha(allocator),
         "available_memory_bytes": available, "options_sha256": options_hash,
         "pause_seconds": 15 if paper else 0, "optimized_flags": flags})
    values = {}
    for variant, extra in (("baseline", []), ("optimized", flags)):
        work = out / variant
        shutil.copytree(VENDOR / "rocksdb-historical", work, ignore=IGNORE)
        # Preserve the experimental baseline used by the historical campaign;
        # the flags, not a different parent revision, select before/after.
        run(["patch", "--batch", "-p1", "-i", ART / "patches/rocksdb-historical.patch"], cwd=work, log=out / f"{variant}-build.log")
        # Refuse a silent no-op experiment against pristine upstream source.
        for definition in flags:
            macro = definition.split("=")[0]
            header = "memtable/skiplist.h" if args.memtable == "prefix_hash" else "memtable/inlineskiplist.h"
            if macro not in (work / "Makefile").read_text() or macro not in (work / header).read_text():
                raise RuntimeError(f"Missing implementation/build support for {macro}")
        run(["make", f"-j{args.jobs}", "db_bench", "DEBUG_LEVEL=0", "PORTABLE=1", "DISABLE_WARNING_AS_ERROR=1", *extra],
            cwd=work, log=out / f"{variant}-build.log")
        save(out / f"{variant}-binary.json", {"sha256": hashlib.sha256((work / "db_bench").read_bytes()).hexdigest(),
             "flags": extra, "source_revision": "19e4aba3db75bd6add7177164c892ab6cdfd50b3 + rocksdb-historical.patch"})
        values[variant] = []
    order = schedule(list(values), reps, args.trial_order or "interleaved")
    save(out / "execution.json", {"sequence": order, "order": args.trial_order or "interleaved"})
    for variant, rep in order:
        work = out / variant
        extra = flags if variant == "optimized" else []
        trial = out / f"{variant}-rep{rep+1}"
        trial.mkdir()
        cmd = placement + [str(work / "db_bench"), f"--db={trial / 'db'}", "--use_existing_db=0",
            f"--benchmarks={benchmarks}", f"--key_size={args.rocks_key_size}", f"--prefix_size={args.rocks_key_size}",
            f"--value_size={args.rocks_value_size}", f"--num={keys}", f"--threads={threads-1}",
            "--disable_wal=1", "--sync=0", f"--duration={duration}", *workload_options]
        save(trial / "config.json", {"command": cmd, "build_flags": extra, "allocator": env["LD_PRELOAD"],
             "allocator_sha256": rocksdb_memoryonly.sha(allocator), "options_sha256": options_hash,
             "environment": {key: env.get(key) for key in ("LD_PRELOAD", "LD_LIBRARY_PATH", "GLIBC_TUNABLES", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
             "profile": args.profile})
        run(cmd, cwd=work, log=trial / "benchmark.log", env=env, timeout=7200 if paper else 180)
        validation = rocksdb_memoryonly.validate(trial, options_file) if memory_only else rocksdb_hashskiplist.validate(trial, threads, args.rocks_key_size)
        save(trial / "persistence.json", validation)
        matches = re.findall(r"readwhilewriting\s*:\s*[\d.]+\s+micros/op\s+([\d.]+)\s+ops/sec", (trial / "benchmark.log").read_text())
        if not matches: raise RuntimeError(f"No throughput in {trial / 'benchmark.log'}")
        values[variant].append(float(matches[-1]))
        if paper: time.sleep(15)
    summary = compare(values); summary["profile"] = args.profile; summary["memtable"] = args.memtable
    summary["persistence"] = persistence
    save(out / "summary.json", summary)
    print(json.dumps(summary, indent=2))

def experiment(args):
    work = ART / "experiments" / args.name
    if any((work / name).exists() for name in ("work", "results.tsv", "protocol.json")):
        raise RuntimeError(f"This experiment already has build files or results at {work}. Keep this copy and repeat the experiment in a fresh artifact extraction or checkout; the Docker image can be reused.")
    env = os.environ.copy()
    env["JOBS"] = str(args.jobs)
    env["ARTIFACT_PROFILE"] = args.profile
    env["PAGES_PER_TYPE"] = "1"
    env["REPS"] = str(args.reps or (10 if args.profile == "paper" else 1))
    if args.profile == "smoke":
        env.update(THREADS="2", INITIAL="4096", RANGE="8192", DURATION_MS="1000", RUN_SECONDS="3", PERFBENCH_PERF="off", ARTIFACT_NO_NUMA="1")
    if args.name.endswith("_bench"):
        smoke = args.profile == "smoke"
        default_threads = {"ascylib_efrb_bench": 4, "ascylib_dvy_bench": 8}.get(args.name, 24)
        default_memory = "interleave" if args.name in {"ascylib_efrb_bench", "ascylib_dvy_bench"} else "bind"
        threads = args.threads or (min(2, len(os.sched_getaffinity(0))) if smoke else default_threads)
        env.update(THREADS=str(threads), PERFBENCH_NODE=str(args.server_node),
                   PERFBENCH_MEMORY=memory_option(args, default_memory), PERFBENCH_ORDER=args.trial_order or "interleaved",
                   ARTIFACT_NO_NUMA="1" if smoke and not (args.cpus or args.memory_policy) else "0")
        if env["ARTIFACT_NO_NUMA"] == "0":
            env["PERFBENCH_CPUS"] = ",".join(map(str, node_cpus(args.server_node, threads, args.cpus)))
        else:
            env.pop("PERFBENCH_CPUS", None)
        if args.name.startswith("ascylib_"):
            initial = args.initial or (4096 if smoke else (262144 if args.name == "ascylib_efrb_bench" else 1048576))
            rounded = 1 << (initial - 1).bit_length()
            key_range = args.range or 2 * rounded
            if key_range < rounded:
                raise ValueError("--range must cover --initial rounded up to a power of two")
            env.update(INITIAL=str(initial), RANGE=str(key_range),
                       DURATION_MS=str(args.duration_ms or (1000 if smoke else 5000)),
                       UPDATE_PCT=str(args.update_pct if args.update_pct is not None else 0))
        if args.name == "ascylib_hj_bench":
            version = args.hj_jemalloc or "5.3"
            env["HJ_JEMALLOC"] = version
        if args.name == "ascylib_dvy_bench":
            env["DVY_HUGEPAGES"] = args.dvy_hugepages or "auto"
        fields = ("THREADS", "REPS", "INITIAL", "RANGE", "DURATION_MS", "UPDATE_PCT",
                  "PERFBENCH_NODE", "PERFBENCH_CPUS", "PERFBENCH_MEMORY", "PERFBENCH_ORDER",
                  "PERFBENCH_PERF", "ARTIFACT_NO_NUMA", "HJ_JEMALLOC", "DVY_HUGEPAGES")
        save(work / "protocol.json", {"arguments": vars(args), "platform": platform.platform(),
             "allowed_cpus": sorted(os.sched_getaffinity(0)),
             "settings": {key: env[key] for key in fields if key in env}})
    run(["bash", work / "run.sh"], env=env)

def factorization(args, out):
    paper = args.profile == "paper"
    alignment = args.factors == "alignment"
    if alignment:
        cells = {"packed": "", "separated_unaligned32": "HNSWLIB_LAYOUT_VECTOR_SOA64=1,HNSWLIB_LAYOUT_VECTOR_BASE_OFFSET=32",
                 "separated_aligned64": "HNSWLIB_LAYOUT_VECTOR_SOA64=1,HNSWLIB_LAYOUT_VECTOR_BASE_OFFSET=0"}
        import itertools
        orders = list(itertools.permutations(cells))
        blocks = args.reps or (6 if paper else 1)
        source = VENDOR / "hnswlib-sep-align"
    else:
        cells = {"baseline": "", "vector_soa64": "HNSWLIB_LAYOUT_VECTOR_SOA64=1", "hugepage": "HNSWLIB_LAYOUT_MADVISE_HUGEPAGE=1",
                 "both": "HNSWLIB_LAYOUT_VECTOR_SOA64=1,HNSWLIB_LAYOUT_MADVISE_HUGEPAGE=1"}
        orders = [("baseline", "vector_soa64", "hugepage", "both"), ("vector_soa64", "both", "baseline", "hugepage"),
                  ("hugepage", "baseline", "both", "vector_soa64"), ("both", "hugepage", "vector_soa64", "baseline")]
        blocks = args.reps or (10 if paper else 1)
        source = VENDOR / "hnswlib-corrected"
    save(out / "design.json", {"cells": cells, "orders": orders, "blocks": blocks, "profile": args.profile,
                               "source": str(source), "note": "Fresh index per cell; compiler/environment recorded separately."})
    execution = [(label,block) for block in range(1,blocks+1) for label in orders[(block-1)%len(orders)]]
    values = hnsw_campaign.execute(args,out,source,cells,execution,sys.modules[__name__])
    baseline = "packed" if alignment else "baseline"
    summary = compare({"baseline":values[baseline], **{k:v for k,v in values.items() if k!=baseline}})
    save(out / "summary.json", summary)
    if blocks == (6 if alignment else 10):
        summarizer = "summarize_hnsw_alignment.py" if alignment else "summarize_hnsw_factorization.py"
        run([sys.executable, ART / "lib" / summarizer, out])
    else: print("Trials completed; the retained paper summarizer requires exactly 6 alignment or 10 huge-page blocks. Raw CSVs are available.")

def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["doctor", "history", "export", "smoke", "hnsw", "hnsw-factorization", "valkey", "rocksdb", "gui", "experiment", "legacy", "all-performance"],
                   help="Select an action; legacy is a compatibility alias for experiment")
    p.add_argument("name", nargs="?", choices=EXPERIMENTS, help="Benchmark or trace name for the experiment command")
    p.add_argument("--profile", choices=["smoke", "paper"], default="smoke")
    p.add_argument("--out", help="NEW result directory; never overwrite existing results")
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--reps", type=int)
    p.add_argument("--threads", type=int, help="ASCYLIB/TPC-C workers; RocksDB readers plus writer; HNSW build/query threads")
    p.add_argument("--cpus", help="Performance-run CPU list (e.g. 0-7); HashSkipList allows SMT across two nodes; other benchmarks use distinct physical cores")
    p.add_argument("--memory-policy", choices=["bind", "interleave"], help="Memory placement (default: bind; standalone EFRB/DVY: interleave on --server-node; HashSkipList: interleave across --rocks-nodes)")
    p.add_argument("--trial-order", choices=["interleaved", "blocked"], help="ASCYLIB/TPC-C/RocksDB/HNSW repetition order (default: interleaved)")
    p.add_argument("--initial", type=int, help="ASCYLIB requested initial keys; rounded up to a power of two")
    p.add_argument("--range", type=int, help="ASCYLIB key range (default: twice the rounded initial size)")
    p.add_argument("--duration-ms", type=int, help="ASCYLIB measurement duration in milliseconds")
    p.add_argument("--update-pct", type=int, help="ASCYLIB percentage of update operations (default: 0)")
    p.add_argument("--hj-jemalloc", choices=["5.3", "5.0"], help="HJ comparison allocator (default: retained jemalloc 5.3)")
    p.add_argument("--dvy-hugepages", choices=["auto", "require", "off"],
                   help="DVY only: request huge pages for every layout (auto, default); require verified backing before timing; or turn allocator advice off")
    p.add_argument("--dim", type=int, help="Run one HNSW dimension (hnsw paper default: both 128 and 1536; smoke: 128; factorization: 768)")
    p.add_argument("--hnsw-source", choices=["original", "corrected"], help="HNSW before/after source (default: corrected, advises before first touch); original preserves the earlier implementation")
    p.add_argument("--server-node", type=int, default=0)
    p.add_argument("--client-node", type=int, default=1)
    p.add_argument("--memtable", choices=["prefix_hash", "skip_list"], default="prefix_hash")
    p.add_argument("--rocks-key-size", type=int, default=32, help="RocksDB key and prefix bytes (default: 32)")
    p.add_argument("--rocks-value-size", type=int, default=128, help="RocksDB value bytes (default: 128)")
    p.add_argument("--rocks-nodes", type=int, nargs=2, metavar=("NODE_A", "NODE_B"),
                   help="HashSkipList NUMA nodes (default: 0 1); equal logical CPU counts, including SMT, on each")
    p.add_argument("--factors", choices=["hugepage", "alignment"], default="hugepage")
    args = p.parse_args(argv)
    if args.command in {"experiment", "legacy"} and not args.name: p.error("experiment requires a name")
    if args.jobs < 1 or (args.reps is not None and args.reps < 1): p.error("jobs/reps must be positive")
    if min(args.rocks_key_size, args.rocks_value_size) < 1: p.error("RocksDB sizes must be positive")
    if args.rocks_nodes is not None:
        if args.command != "all-performance" and not (args.command == "rocksdb" and args.memtable == "prefix_hash"):
            p.error("rocks-nodes applies only to HashSkipList or all-performance")
        if min(args.rocks_nodes) < 0 or args.rocks_nodes[0] == args.rocks_nodes[1]:
            p.error("rocks-nodes requires two distinct nonnegative NUMA nodes")
    if any(value is not None and value < 1 for value in (args.threads, args.initial, args.range, args.duration_ms, args.dim)):
        p.error("threads/initial/range/duration-ms/dim must be positive")
    if args.update_pct is not None and not 0 <= args.update_pct <= 100: p.error("update-pct must be 0..100")
    bench = args.command in {"experiment", "legacy"} and args.name and args.name.endswith("_bench")
    hnsw_command = args.command in {"hnsw", "hnsw-factorization"}
    if (args.threads is not None or args.cpus is not None) and not (bench or args.command == "rocksdb" or hnsw_command):
        p.error("threads/cpus apply to individual ASCYLIB/TPC-C/RocksDB/HNSW performance experiments")
    if args.memory_policy and not (bench or args.command in {"rocksdb", "all-performance"} or hnsw_command):
        p.error("memory-policy applies to performance experiments")
    if args.trial_order and not (bench or args.command in {"rocksdb", "all-performance", "hnsw"}):
        p.error("trial-order applies to ASCYLIB/TPC-C/RocksDB/HNSW; factorization uses its fixed design")
    if args.dim is not None and not hnsw_command: p.error("dim applies only to HNSW commands")
    if args.hnsw_source is not None and args.command != "hnsw": p.error("hnsw-source applies only to hnsw; factorization selects its source")
    if args.hj_jemalloc is not None and not (bench and args.name == "ascylib_hj_bench"):
        p.error("hj-jemalloc applies only to ascylib_hj_bench")
    if args.dvy_hugepages is not None and not (bench and args.name == "ascylib_dvy_bench"):
        p.error("dvy-hugepages applies only to ascylib_dvy_bench")
    if any(v is not None for v in (args.initial, args.range, args.duration_ms, args.update_pct)) and not (bench and args.name.startswith("ascylib_")):
        p.error("initial/range/duration-ms/update-pct apply only to ASCYLIB performance experiments")
    if args.command == "rocksdb" and args.threads == 1: p.error("RocksDB requires a reader and a writer (at least 2 threads)")
    return args

def main():
    args = parse_args()
    if args.command == "doctor": doctor()
    elif args.command == "history": history()
    elif args.command == "gui": gui()
    elif args.command in {"experiment", "legacy"}:
        experiment(args)
    elif args.command == "all-performance":
        for name in [x for x in EXPERIMENTS if x.endswith("_bench")]:
            args.name = name; experiment(args)
        args.command = "hnsw"; hnsw(args, new_output(args))
        args.command = "valkey"; valkey(args, new_output(args))
        for memtable in ("prefix_hash", "skip_list"):
            args.command = "rocksdb"; args.memtable = memtable; rocksdb(args, new_output(args))
    else:
        out = new_output(args)
        try:
            if args.command == "smoke": doctor(); history(); export(out)
            elif args.command == "export": export(out)
            elif args.command == "hnsw": hnsw(args, out)
            elif args.command == "valkey": valkey(args, out)
            elif args.command == "rocksdb": rocksdb(args, out)
            elif args.command == "hnsw-factorization": factorization(args, out)
            save(out / "status.json", {"status": "passed", "scope": args.command, "profile": args.profile})
        except Exception as exc:
            save(out / "status.json", {"status": "failed", "error": str(exc)})
            raise
        print("Results:", out)

if __name__ == "__main__":
    main()
