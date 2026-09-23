#!/usr/bin/env python3
"""Authoritative Valkey/memtier baseline benchmark."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


IMAGE_DEFAULT = "sifter-valkey-memtier"
BASE_IMAGE_DEFAULT = "sifter"
CONTAINER_SIFTER_ROOT = Path("/root/sifter")

SERVER_NUMA_NODE = 0
CLIENT_NUMA_NODE = 1
PORT_DEFAULT = 16379

KEY_MINIMUM = 1
KEY_MAXIMUM = 1_000_000
DATA_SIZE = 128
TEST_TIME_SECONDS = 30
MEMTIER_CLIENTS = 4
MEMTIER_PIPELINE = 16
KEY_PREFIX = "heaplens:"
MEASURED_RATIO = "1:4"
PRELOAD_RATIO = "1:0"
MALLOC_BACKENDS = ("libc", "jemalloc")
PERF_EVENTS_DEFAULT = "cache-references,cache-misses,dtlb-loads,dtlb-load-misses"


class BenchmarkError(RuntimeError):
    pass


def validate_ratio(value: str) -> str:
    parts = value.split(":")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("ratio must use memtier set:get form, for example 1:4")
    try:
        sets, gets = (int(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ratio components must be non-negative integers") from exc
    if sets < 0 or gets < 0 or sets + gets <= 0:
        raise argparse.ArgumentTypeError("ratio must include at least one set or get operation")
    return value


def benchmark_name(ratio: str) -> str:
    return f"valkey-memtier-cross-node-cache-ratio-{ratio.replace(':', '-')}"


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fixed cross-node Valkey/memtier benchmark used as the "
            "authoritative baseline."
        )
    )
    parser.add_argument(
        "--build-image",
        action="store_true",
        help="Build the Docker image before running the benchmark.",
    )
    parser.add_argument(
        "--image",
        default=IMAGE_DEFAULT,
        help=f"Docker image to use or build. Default: {IMAGE_DEFAULT}.",
    )
    parser.add_argument(
        "--base-image",
        default=BASE_IMAGE_DEFAULT,
        help=f"Base Docker image when --build-image is used. Default: {BASE_IMAGE_DEFAULT}.",
    )
    parser.add_argument(
        "--run-dir",
        help=(
            "Artifact directory. On the host this may be relative to the repo "
            "root, an absolute path under the repo root, or a /root/sifter path."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=PORT_DEFAULT,
        help=f"Valkey TCP port inside the container. Default: {PORT_DEFAULT}.",
    )
    parser.add_argument(
        "--no-numa-pin",
        action="store_true",
        help="Disable CPU/memory pinning. This is for portability, not the authoritative profile.",
    )
    parser.add_argument(
        "--malloc-backend",
        choices=MALLOC_BACKENDS,
        default="libc",
        help="Allocator backend for Valkey builds. Default: libc.",
    )
    parser.add_argument(
        "--ratio",
        type=validate_ratio,
        default=MEASURED_RATIO,
        help=(
            "Measured memtier operation ratio in set:get form. "
            f"Default: {MEASURED_RATIO}."
        ),
    )
    parser.add_argument(
        "--key-minimum",
        type=positive_int,
        default=KEY_MINIMUM,
        help=f"Minimum numeric key suffix for memtier. Default: {KEY_MINIMUM}.",
    )
    parser.add_argument(
        "--key-maximum",
        type=positive_int,
        default=KEY_MAXIMUM,
        help=f"Maximum numeric key suffix for memtier. Default: {KEY_MAXIMUM}.",
    )
    parser.add_argument(
        "--perf-stat",
        action="store_true",
        help="Collect perf stat counters for the Valkey server during the measured phase.",
    )
    parser.add_argument(
        "--perf-events",
        default=PERF_EVENTS_DEFAULT,
        help=f"Comma-separated perf events used with --perf-stat. Default: {PERF_EVENTS_DEFAULT}.",
    )
    parser.add_argument(
        "--source-dir",
        default=str(CONTAINER_SIFTER_ROOT / "valkey_bench" / "valkey"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--inside-container",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    if args.key_maximum < args.key_minimum:
        parser.error("--key-maximum must be greater than or equal to --key-minimum")
    return args


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if check and proc.returncode != 0:
        raise BenchmarkError(
            f"command failed with exit code {proc.returncode}: {' '.join(cmd)}\n{proc.stdout}"
        )
    return proc


def run_stream(cmd: list[str], log_path: Path, *, cwd: Path | None = None, echo: bool = True) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            if echo:
                sys.stdout.write(line)
            log.write(line)
        proc.wait()
    if proc.returncode != 0:
        raise BenchmarkError(f"command failed with exit code {proc.returncode}: {' '.join(cmd)}")


def start_perf_stat(args: argparse.Namespace, pid: int, run_dir: Path) -> subprocess.Popen[str] | None:
    if not args.perf_stat:
        return None

    perf = executable("perf")
    if perf is None:
        raise BenchmarkError("perf was not found in PATH")

    perf_csv = run_dir / "perf_stat.csv"
    cmd = [
        perf,
        "stat",
        "-x",
        ",",
        "-e",
        args.perf_events,
        "-p",
        str(pid),
        "-o",
        str(perf_csv),
    ]
    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(0.5)
    if proc.poll() is not None:
        output = proc.stdout.read() if proc.stdout else ""
        raise BenchmarkError(f"perf stat failed to start:\n{output}")
    return proc


def stop_perf_stat(proc: subprocess.Popen[str] | None, run_dir: Path) -> None:
    if proc is None:
        return

    proc.send_signal(signal.SIGINT)
    try:
        output, _ = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        output, _ = proc.communicate()
    if output:
        (run_dir / "perf_stat.log").write_text(output, encoding="utf-8")
    if proc.returncode not in (0, -signal.SIGINT, 128 + signal.SIGINT):
        raise BenchmarkError(f"perf stat failed with exit code {proc.returncode}")


def docker_cmd() -> list[str]:
    if run(["docker", "info"], check=False).returncode == 0:
        return ["docker"]
    if run(["sudo", "-n", "docker", "info"], check=False).returncode == 0:
        return ["sudo", "docker"]
    raise BenchmarkError("Docker is not available. Run with Docker access or sudo docker access.")


def sifter_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def default_container_run_dir() -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return CONTAINER_SIFTER_ROOT / "valkey_bench" / "baseline_runs" / f"cross_node_30s_{stamp}"


def container_run_dir(host_sifter_root: Path, run_dir_arg: str | None) -> Path:
    if run_dir_arg is None:
        return default_container_run_dir()

    raw = Path(run_dir_arg)
    if raw.is_absolute() and str(raw).startswith(str(CONTAINER_SIFTER_ROOT)):
        return raw
    if raw.is_absolute():
        try:
            rel = raw.resolve().relative_to(host_sifter_root.resolve())
        except ValueError as exc:
            raise BenchmarkError(
                f"--run-dir must be under {host_sifter_root} or /root/sifter when running through Docker."
            ) from exc
        return CONTAINER_SIFTER_ROOT / rel
    return CONTAINER_SIFTER_ROOT / raw


def build_image(args: argparse.Namespace, host_sifter_root: Path, docker: list[str]) -> None:
    bench_root = host_sifter_root / "valkey_bench"
    cmd = [
        *docker,
        "build",
        "-f",
        str(bench_root / "docker" / "Dockerfile"),
        "--build-arg",
        f"BASE_IMAGE={args.base_image}",
        str(bench_root),
        "-t",
        args.image,
    ]
    run_stream(cmd, bench_root / "baseline_runs" / "docker_build.log")


def image_exists(image: str, docker: list[str]) -> bool:
    return run([*docker, "image", "inspect", image], check=False).returncode == 0


def run_in_docker(args: argparse.Namespace) -> None:
    host_sifter_root = sifter_root_from_script()
    docker = docker_cmd()

    if args.build_image:
        build_image(args, host_sifter_root, docker)
    elif not image_exists(args.image, docker):
        raise BenchmarkError(
            f"Docker image '{args.image}' was not found. Re-run with --build-image."
        )

    run_dir = container_run_dir(host_sifter_root, args.run_dir)
    container_cmd = [
        "python3",
        str(CONTAINER_SIFTER_ROOT / "valkey_bench" / "benchmark.py"),
        "--inside-container",
        "--run-dir",
        str(run_dir),
        "--port",
        str(args.port),
        "--malloc-backend",
        args.malloc_backend,
        "--ratio",
        args.ratio,
        "--key-minimum",
        str(args.key_minimum),
        "--key-maximum",
        str(args.key_maximum),
    ]
    if args.no_numa_pin:
        container_cmd.append("--no-numa-pin")
    if args.perf_stat:
        container_cmd.extend(["--perf-stat", "--perf-events", args.perf_events])

    cmd = [
        *docker,
        "run",
        "--rm",
        "--privileged",
        "-v",
        f"{host_sifter_root}:{CONTAINER_SIFTER_ROOT}",
        "-w",
        str(CONTAINER_SIFTER_ROOT),
        args.image,
        *container_cmd,
    ]
    subprocess.run(cmd, check=True)


def parse_lscpu() -> list[dict[str, int | str]]:
    proc = run(["lscpu", "-p=CPU,NODE,CORE,ONLINE"])
    rows: list[dict[str, int | str]] = []
    for line in proc.stdout.splitlines():
        if not line or line.startswith("#"):
            continue
        cpu, node, core, online = line.split(",")
        rows.append(
            {
                "cpu": int(cpu),
                "node": int(node),
                "core": int(core),
                "online": online,
            }
        )
    return rows


def primary_cpus_for_node(node: int) -> list[int]:
    seen_cores: set[int] = set()
    cpus: list[int] = []
    for row in parse_lscpu():
        if row["node"] != node or row["online"] != "Y":
            continue
        core = int(row["core"])
        if core in seen_cores:
            continue
        seen_cores.add(core)
        cpus.append(int(row["cpu"]))
    if not cpus:
        raise BenchmarkError(f"failed to derive primary CPUs for NUMA node {node}")
    return cpus


def cpu_list(cpus: list[int]) -> str:
    return ",".join(str(cpu) for cpu in cpus)


def executable(name: str) -> str | None:
    return shutil.which(name)


def pin_prefix(cpus: list[int], node: int, *, no_numa_pin: bool) -> list[str]:
    if no_numa_pin:
        return []
    cpus_text = cpu_list(cpus)
    if executable("numactl"):
        return ["numactl", f"--physcpubind={cpus_text}", f"--membind={node}"]
    if executable("taskset"):
        return ["taskset", "-c", cpus_text]
    raise BenchmarkError("neither numactl nor taskset is available for CPU pinning")


def copy_valkey(source_dir: Path, work_valkey: Path) -> None:
    if work_valkey.exists():
        raise BenchmarkError(f"worktree already exists: {work_valkey}")

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {".git", "baseline_runs", "heaplens_runs"}
        ignored.update(name for name in names if name.endswith((".o", ".d")))
        ignored.update(
            name
            for name in names
            if name
            in {
                "valkey-server",
                "valkey-sentinel",
                "valkey-cli",
                "valkey-benchmark",
                "valkey-check-aof",
                "valkey-check-rdb",
            }
        )
        return ignored.intersection(names)

    print("==> Copying Valkey into benchmark worktree")
    work_valkey.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, work_valkey, ignore=ignore)


def valkey_malloc_make_arg(malloc_backend: str) -> str:
    if malloc_backend in MALLOC_BACKENDS:
        return f"MALLOC={malloc_backend}"
    raise BenchmarkError(f"unsupported malloc backend: {malloc_backend}")


def build_valkey(work_valkey: Path, build_log: Path, malloc_backend: str) -> None:
    print("==> Building Valkey baseline")
    jobs = os.environ.get("JOBS") or str(os.cpu_count() or 1)
    cmd = [
        "make",
        f"-j{jobs}",
        valkey_malloc_make_arg(malloc_backend),
        "BUILD_TLS=no",
        "BUILD_RDMA=no",
        "BUILD_LUA=no",
        "USE_SYSTEMD=no",
        "V=1",
    ]
    run_stream(cmd, build_log, cwd=work_valkey, echo=False)


def wait_for_server(cli: Path, port: int, server_proc: subprocess.Popen[str], server_log: Path) -> None:
    for _ in range(100):
        if run([str(cli), "-h", "127.0.0.1", "-p", str(port), "ping"], check=False).returncode == 0:
            return
        if server_proc.poll() is not None:
            raise BenchmarkError(f"Valkey server exited during startup. See {server_log}")
        time.sleep(0.1)
    raise BenchmarkError(f"Valkey server did not become ready on port {port}. See {server_log}")


def shutdown_server(cli: Path, port: int, server_proc: subprocess.Popen[str] | None) -> None:
    if server_proc is None or server_proc.poll() is not None:
        return
    run([str(cli), "-h", "127.0.0.1", "-p", str(port), "shutdown", "nosave"], check=False)
    for _ in range(50):
        if server_proc.poll() is not None:
            return
        time.sleep(0.1)
    server_proc.terminate()
    try:
        server_proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        server_proc.kill()


def memtier_common(port: int) -> list[str]:
    memtier = executable("memtier_benchmark")
    if memtier is None:
        raise BenchmarkError("memtier_benchmark was not found in PATH")
    return [memtier, "--server=127.0.0.1", f"--port={port}", "--protocol=redis"]


def memtier_preload_args(client_threads: int, json_path: Path, key_minimum: int, key_maximum: int) -> list[str]:
    return [
        f"--threads={client_threads}",
        f"--clients={MEMTIER_CLIENTS}",
        f"--pipeline={MEMTIER_PIPELINE}",
        f"--ratio={PRELOAD_RATIO}",
        "--key-pattern=P:P",
        f"--key-prefix={KEY_PREFIX}",
        f"--key-minimum={key_minimum}",
        f"--key-maximum={key_maximum}",
        "--requests=allkeys",
        f"--data-size={DATA_SIZE}",
        "--distinct-client-seed",
        "--hide-histogram",
        f"--json-out-file={json_path}",
    ]


def memtier_measured_args(client_threads: int, json_path: Path, ratio: str, key_minimum: int, key_maximum: int) -> list[str]:
    return [
        f"--threads={client_threads}",
        f"--clients={MEMTIER_CLIENTS}",
        f"--pipeline={MEMTIER_PIPELINE}",
        f"--ratio={ratio}",
        "--key-pattern=R:R",
        f"--key-prefix={KEY_PREFIX}",
        f"--key-minimum={key_minimum}",
        f"--key-maximum={key_maximum}",
        f"--data-size={DATA_SIZE}",
        f"--test-time={TEST_TIME_SECONDS}",
        "--distinct-client-seed",
        "--hide-histogram",
        f"--json-out-file={json_path}",
    ]


def parse_info(path: Path, wanted: set[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key in wanted:
            result[key] = value.strip()
    return result


def write_summary(run_dir: Path, config: dict[str, object]) -> None:
    benchmark_json = run_dir / "benchmark.json"
    data = json.loads(benchmark_json.read_text(encoding="utf-8"))
    totals = data["ALL STATS"]["Totals"]
    percentiles = totals["Percentile Latencies"]
    memory = parse_info(
        run_dir / "memory_after.txt",
        {"used_memory", "used_memory_rss", "allocator_frag_ratio", "mem_fragmentation_ratio"},
    )
    stats = parse_info(
        run_dir / "stats_after.txt",
        {
            "total_commands_processed",
            "total_net_input_bytes",
            "total_net_output_bytes",
            "rejected_connections",
        },
    )
    results = {
        "ops_per_sec": totals["Ops/sec"],
        "count": totals["Count"],
        "kb_per_sec": totals["KB/sec"],
        "hits_per_sec": totals["Hits/sec"],
        "misses_per_sec": totals["Misses/sec"],
        "avg_latency_ms": totals["Average Latency"],
        "p50_latency_ms": percentiles["p50.00"],
        "p99_latency_ms": percentiles["p99.00"],
        "p999_latency_ms": percentiles["p99.90"],
        "connection_errors": totals["Connection Errors"],
    }
    summary = {
        "benchmark": benchmark_name(str(config["ratio"])),
        "config": config,
        "results": results,
        "memory_after": memory,
        "stats_after": stats,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        f"benchmark={summary['benchmark']}",
        f"ratio={config['ratio']}",
        f"ops_per_sec={results['ops_per_sec']}",
        f"count={results['count']}",
        f"avg_latency_ms={results['avg_latency_ms']}",
        f"p50_latency_ms={results['p50_latency_ms']}",
        f"p99_latency_ms={results['p99_latency_ms']}",
        f"p999_latency_ms={results['p999_latency_ms']}",
        f"kb_per_sec={results['kb_per_sec']}",
        f"used_memory={memory.get('used_memory', '')}",
        f"used_memory_rss={memory.get('used_memory_rss', '')}",
        f"mem_fragmentation_ratio={memory.get('mem_fragmentation_ratio', '')}",
        f"total_commands_processed={stats.get('total_commands_processed', '')}",
    ]
    (run_dir / "metrics.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("==> Summary")
    for line in lines:
        print(line)


def git_rev(path: Path) -> str:
    if not (path / ".git").exists():
        return "unknown"
    proc = run(
        ["git", "-c", f"safe.directory={path}", "-C", str(path), "rev-parse", "--short", "HEAD"],
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def run_inside_container(args: argparse.Namespace) -> None:
    source_dir = Path(args.source_dir)
    if not (source_dir / "src").is_dir():
        raise BenchmarkError(f"Valkey source directory not found: {source_dir}")

    run_dir = Path(args.run_dir or default_container_run_dir())
    run_dir.mkdir(parents=True, exist_ok=True)
    work_valkey = run_dir / "work" / "valkey"

    server_cpus = primary_cpus_for_node(SERVER_NUMA_NODE)
    client_cpus = primary_cpus_for_node(CLIENT_NUMA_NODE)
    server_threads = len(server_cpus)
    client_threads = len(client_cpus)

    config = {
        "layout": "cross-node",
        "malloc_backend": args.malloc_backend,
        "valkey_make_malloc": valkey_malloc_make_arg(args.malloc_backend),
        "server_numa_node": SERVER_NUMA_NODE,
        "client_numa_node": CLIENT_NUMA_NODE,
        "server_cpus": cpu_list(server_cpus),
        "client_cpus": cpu_list(client_cpus),
        "server_io_threads": server_threads,
        "memtier_threads": client_threads,
        "memtier_clients": MEMTIER_CLIENTS,
        "memtier_pipeline": MEMTIER_PIPELINE,
        "ratio": args.ratio,
        "preload_ratio": PRELOAD_RATIO,
        "key_minimum": args.key_minimum,
        "key_maximum": args.key_maximum,
        "key_prefix": KEY_PREFIX,
        "data_size": DATA_SIZE,
        "test_time_seconds": TEST_TIME_SECONDS,
        "port": args.port,
        "numa_pin": not args.no_numa_pin,
        "perf_stat": args.perf_stat,
        "perf_events": args.perf_events if args.perf_stat else "",
        "valkey_source": str(source_dir),
        "valkey_commit": git_rev(source_dir),
    }
    (run_dir / "benchmark_config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    build_log = run_dir / "build.log"
    server_log = run_dir / "server.log"
    preload_log = run_dir / "preload.log"
    benchmark_log = run_dir / "benchmark.log"
    preload_json = run_dir / "preload.json"
    benchmark_json = run_dir / "benchmark.json"
    memory_after = run_dir / "memory_after.txt"
    stats_after = run_dir / "stats_after.txt"

    copy_valkey(source_dir, work_valkey)
    build_valkey(work_valkey, build_log, args.malloc_backend)

    server = work_valkey / "src" / "valkey-server"
    cli = work_valkey / "src" / "valkey-cli"
    server_cmd = [
        *pin_prefix(server_cpus, SERVER_NUMA_NODE, no_numa_pin=args.no_numa_pin),
        str(server),
        "--bind",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--protected-mode",
        "no",
        "--save",
        "",
        "--appendonly",
        "no",
        "--daemonize",
        "no",
        "--dir",
        str(run_dir),
        "--logfile",
        str(server_log),
        "--io-threads",
        str(server_threads),
        "--io-threads-always-active",
        "yes",
    ]
    client_prefix = pin_prefix(client_cpus, CLIENT_NUMA_NODE, no_numa_pin=args.no_numa_pin)

    print(
        "==> Fixed profile: cross-node "
        f"server_node={SERVER_NUMA_NODE} server_cpus={config['server_cpus']} "
        f"client_node={CLIENT_NUMA_NODE} client_cpus={config['client_cpus']}"
    )
    print(f"==> Starting Valkey server on port {args.port}")
    server_proc: subprocess.Popen[str] | None = None
    try:
        server_proc = subprocess.Popen(server_cmd, text=True)
        wait_for_server(cli, args.port, server_proc, server_log)

        common = memtier_common(args.port)
        print("==> Running memtier preload")
        run_stream(
            [*client_prefix, *common, *memtier_preload_args(client_threads, preload_json, args.key_minimum, args.key_maximum)],
            preload_log,
        )

        print("==> Running measured memtier benchmark")
        perf_proc = start_perf_stat(args, server_proc.pid, run_dir)
        try:
            run_stream(
                [
                    *client_prefix,
                    *common,
                    *memtier_measured_args(client_threads, benchmark_json, args.ratio, args.key_minimum, args.key_maximum),
                ],
                benchmark_log,
            )
        finally:
            stop_perf_stat(perf_proc, run_dir)

        print("==> Capturing INFO memory/stats")
        memory_after.write_text(
            run([str(cli), "-h", "127.0.0.1", "-p", str(args.port), "info", "memory"], check=False).stdout,
            encoding="utf-8",
        )
        stats_after.write_text(
            run([str(cli), "-h", "127.0.0.1", "-p", str(args.port), "info", "stats"], check=False).stdout,
            encoding="utf-8",
        )
    finally:
        print("==> Shutting down Valkey")
        shutdown_server(cli, args.port, server_proc)

    write_summary(run_dir, config)
    print("Done.")
    print(f"Run directory: {run_dir}")
    print(f"Summary:       {run_dir / 'summary.json'}")
    print(f"Metrics:       {run_dir / 'metrics.txt'}")


def main() -> int:
    args = parse_args()
    try:
        if args.inside_container:
            run_inside_container(args)
        else:
            run_in_docker(args)
    except (BenchmarkError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        print("Interrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
