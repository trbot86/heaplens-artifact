#!/usr/bin/env python3
"""Docker-first Valkey/memtier HeapLENS trace benchmark."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence


IMAGE_DEFAULT = "sifter-valkey-memtier-heaplens"
BASE_IMAGE_DEFAULT = "sifter"
CONTAINER_SIFTER_ROOT = Path("/root/sifter")
CONTAINER_BENCH_ROOT = CONTAINER_SIFTER_ROOT / "valkey_bench_heaplens"

BENCHMARK_ID = "valkey-heaplens-cross-node-cache-80-20"
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

SEMANTIC_ALLOCATOR_SOURCE_NAMES = frozenset(
    {
        "zmalloc",
        "zmalloc_cache_aligned",
        "zcalloc",
        "zcalloc_num",
        "zrealloc",
        "ztrymalloc",
        "ztrycalloc",
        "ztryrealloc",
        "zmalloc_usable",
        "zcalloc_usable",
        "zrealloc_usable",
        "ztrymalloc_usable",
        "ztrycalloc_usable",
        "ztryrealloc_usable",
        "zstrdup",
        "s_malloc",
        "s_realloc",
        "s_trymalloc",
        "s_tryrealloc",
        "s_malloc_usable",
        "s_realloc_usable",
        "s_trymalloc_usable",
        "s_tryrealloc_usable",
        "lp_malloc",
        "lp_realloc",
        "rax_malloc",
        "rax_realloc",
        "valkey_malloc",
        "valkey_malloc_cache_aligned",
        "valkey_calloc",
        "valkey_calloc_num",
        "valkey_realloc",
        "valkey_trymalloc",
        "valkey_trycalloc",
        "valkey_tryrealloc",
        "valkey_malloc_usable",
        "valkey_calloc_usable",
        "valkey_realloc_usable",
        "valkey_trymalloc_usable",
        "valkey_trycalloc_usable",
        "valkey_tryrealloc_usable",
        "valkey_strdup",
    }
)

VALKEY_BUILD_FLAGS = [
    "BUILD_TLS=no",
    "BUILD_RDMA=no",
    "BUILD_LUA=no",
    "USE_SYSTEMD=no",
]
MEMHOOK_CFLAGS = "-D_GNU_SOURCE -D_DEFAULT_SOURCE -DHEAPLENS_VALKEY_SEMANTIC_ALLOC -I/root/sifter/memhook"
MEMHOOK_LIBS = "-L/root/sifter/memhook -Wl,-rpath=/root/sifter/memhook -lmemhook -ldl"
MALLOC_BACKENDS = ("libc", "jemalloc")


class BenchmarkError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Instrument Valkey with Sifter/HeapLENS inside Docker, run the fixed "
            "cross-node memtier profile, and convert the allocation trace to SQLite."
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
        "--sample",
        type=float,
        default=0.1,
        help="Page sampling probability for SQLite conversion. Default: 0.1.",
    )
    parser.add_argument(
        "--pages-per-type",
        type=int,
        default=2,
        help="Minimum backup sampled pages per type. Default: 2.",
    )
    parser.add_argument(
        "--db-threads",
        type=int,
        default=1,
        help="Thread count passed to convert_to_db. Default: 1.",
    )
    parser.add_argument(
        "--no-numa-pin",
        action="store_true",
        help="Disable CPU/memory pinning. This is for portability, not the authoritative profile.",
    )
    parser.add_argument(
        "--trace-measured",
        action="store_true",
        help=(
            "Also run the 30s measured phase with memhook logging enabled. "
            "Default traces preload only and measures throughput on a no-HeapLENS server."
        ),
    )
    parser.add_argument(
        "--malloc-backend",
        choices=MALLOC_BACKENDS,
        default="libc",
        help="Allocator backend for Valkey builds. Default: libc.",
    )
    parser.add_argument(
        "--source-dir",
        default=str(CONTAINER_BENCH_ROOT / "valkey"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--inside-container",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def run(
    cmd: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if check and proc.returncode != 0:
        raise BenchmarkError(
            f"command failed with exit code {proc.returncode}: {shlex.join(cmd)}\n{proc.stdout}"
        )
    return proc


def run_stream(
    cmd: Sequence[str],
    log_path: Path,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    echo: bool = True,
    check: bool = True,
    mode: str = "w",
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open(mode, encoding="utf-8") as log:
        log.write(f"$ {shlex.join(cmd)}\n")
        proc = subprocess.Popen(
            list(cmd),
            cwd=str(cwd) if cwd else None,
            env=env,
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
        log.write(f"\nexit_code={proc.returncode}\n")
    if check and proc.returncode != 0:
        raise BenchmarkError(
            f"command failed with exit code {proc.returncode}: {shlex.join(cmd)}\nSee {log_path}"
        )
    return int(proc.returncode)


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
    return CONTAINER_BENCH_ROOT / "heaplens_runs" / f"cross_node_30s_{stamp}"


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
    bench_root = host_sifter_root / "valkey_bench_heaplens"
    log_path = bench_root / "heaplens_runs" / "docker_build.log"
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
    run_stream(cmd, log_path)


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
        str(CONTAINER_BENCH_ROOT / "benchmark.py"),
        "--inside-container",
        "--run-dir",
        str(run_dir),
        "--port",
        str(args.port),
        "--sample",
        str(args.sample),
        "--pages-per-type",
        str(args.pages_per_type),
        "--db-threads",
        str(args.db_threads),
        "--malloc-backend",
        args.malloc_backend,
    ]
    if args.no_numa_pin:
        container_cmd.append("--no-numa-pin")
    if args.trace_measured:
        container_cmd.append("--trace-measured")

    cmd = [
        *docker,
        "run",
        "--rm",
        "--privileged",
        "--ulimit",
        "nofile=1048576:1048576",
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


def make_jobs() -> str:
    return os.environ.get("JOBS") or str(os.cpu_count() or 1)


def valkey_malloc_make_arg(malloc_backend: str) -> str:
    if malloc_backend in MALLOC_BACKENDS:
        return f"MALLOC={malloc_backend}"
    raise BenchmarkError(f"unsupported malloc backend: {malloc_backend}")


def valkey_make_cmd(jobs: str, *, with_memhook: bool, malloc_backend: str) -> list[str]:
    cmd = ["make", f"-j{jobs}", valkey_malloc_make_arg(malloc_backend), *VALKEY_BUILD_FLAGS, "V=1"]
    if with_memhook:
        cmd.append(f"SERVER_CFLAGS={MEMHOOK_CFLAGS}")
    return cmd


def copy_clean_valkey(source_dir: Path, clean_source: Path) -> None:
    if clean_source.exists():
        raise BenchmarkError(f"clean source worktree already exists: {clean_source}")

    def ignore(_directory: str, names: list[str]) -> set[str]:
        ignored = {
            ".git",
            "baseline_runs",
            "heaplens_runs",
            "compile_commands.json",
            "fixes.yaml",
            "fielddump.txt",
            "fileset_dump.txt",
            "typeset_dump.txt",
            "binary_dump.txt",
            ".make-settings",
            "valkey-server",
            "valkey-sentinel",
            "valkey-cli",
            "valkey-benchmark",
            "valkey-check-aof",
            "valkey-check-rdb",
        }
        ignored.update(name for name in names if name.endswith((".o", ".d", ".a", ".so", ".gcda", ".gcno")))
        return ignored.intersection(names)

    print("==> Preparing clean Valkey input tree for Sifter")
    clean_source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, clean_source, ignore=ignore)


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def write_compile_commands_helper(run_dir: Path, jobs: str, malloc_backend: str) -> Path:
    helper = run_dir / "work" / "build_and_filter_compile_commands.sh"
    build_cmd = shlex.join(
        ["bear", "--", *valkey_make_cmd(jobs, with_memhook=False, malloc_backend=malloc_backend)]
    )
    helper.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
make distclean
if [ ! -f deps/jemalloc/configure ]; then (cd deps/jemalloc && autoconf); fi
{build_cmd}
python3 - <<'PY'
import json
from pathlib import Path
from posixpath import basename

path = Path("compile_commands.json")
entries = json.loads(path.read_text())
keep = []
seen = set()
excluded = {{
    "valkey-benchmark.c",
    "valkey-cli.c",
    "valkey-check-aof.c",
    "valkey-check-rdb.c",
}}
for entry in entries:
    file_name = entry.get("file", "")
    source = Path(file_name)
    if not source.is_absolute():
        source = Path(entry.get("directory", ".")) / source
    try:
        source.resolve().relative_to((Path.cwd() / "src").resolve())
    except ValueError:
        continue
    normalized = file_name.replace("\\\\", "/")
    if "/src/" not in normalized and not normalized.startswith("src/"):
        continue
    if "/src/unit/" in normalized:
        continue
    if not normalized.endswith(".c"):
        continue
    if basename(normalized) in excluded:
        continue
    if normalized in seen:
        continue
    seen.add(normalized)
    if normalized.endswith("/src/zmalloc.c") or normalized == "src/zmalloc.c" or normalized == "zmalloc.c":
        continue
    if "zmalloc" in normalized:
        continue
    if normalized:
        keep.append(entry)
if not keep:
    raise SystemExit("compile_commands.json did not contain server-side Valkey src/*.c entries")
path.write_text(json.dumps(keep, indent=2) + "\\n")
PY
""",
        encoding="utf-8",
    )
    helper.chmod(0o755)
    return helper


def container_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(CONTAINER_SIFTER_ROOT))
    except ValueError as exc:
        raise BenchmarkError(f"path must be under {CONTAINER_SIFTER_ROOT}: {path}") from exc


def yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def parse_fix_blocks(text: str) -> tuple[list[str], list[list[str]], list[str]]:
    header: list[str] = []
    footer: list[str] = []
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("- BuildDirectory:"):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif line.startswith("MainSourceFile:"):
            if current is not None:
                blocks.append(current)
                current = None
            footer.append(line)
        elif current is None:
            header.append(line)
        else:
            current.append(line)
    if current is not None:
        blocks.append(current)
    return header, blocks, footer


def block_message(block: list[str]) -> str:
    for line in block:
        stripped = line.strip()
        if stripped.startswith("Message:"):
            return yaml_scalar(stripped.split(":", 1)[1])
    return ""


def block_build_dir(block: list[str]) -> Path:
    for line in block:
        if line.startswith("- BuildDirectory:"):
            return Path(yaml_scalar(line.split(":", 1)[1]))
    raise BenchmarkError("missing BuildDirectory in fixes.yaml block")


def replacement_for_block(block: list[str]) -> tuple[Path, int, int, str] | None:
    build_dir = block_build_dir(block)
    replacement_file: Path | None = None
    offset: int | None = None
    length: int | None = None
    replacement_text: str | None = None

    for line in block:
        stripped = line.strip()
        if stripped.startswith("- FilePath:"):
            raw = yaml_scalar(stripped.split(":", 1)[1])
            replacement_file = Path(raw)
        elif stripped.startswith("Offset:"):
            offset = int(stripped.split(":", 1)[1].strip())
        elif stripped.startswith("Length:"):
            length = int(stripped.split(":", 1)[1].strip())
        elif stripped.startswith("ReplacementText:"):
            replacement_text = yaml_scalar(stripped.split(":", 1)[1])

    if replacement_file is None or offset is None or length is None or replacement_text is None:
        return None
    source_path = replacement_file if replacement_file.is_absolute() else build_dir / replacement_file
    return source_path, offset, length, replacement_text


def identifier_before_offset(source_path: Path, offset: int) -> str:
    if not source_path.exists():
        return ""
    text = source_path.read_text(encoding="utf-8", errors="replace")
    if offset < 0 or offset > len(text):
        return ""
    match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", text[:offset])
    return match.group(1) if match else ""


def filter_fixes_to_semantic_allocators(fixes_path: Path, original_copy: Path) -> int:
    if not fixes_path.exists():
        raise BenchmarkError(f"Sifter did not produce fixes.yaml at {fixes_path}")

    text = fixes_path.read_text(encoding="utf-8")
    original_copy.write_text(text, encoding="utf-8")

    header, blocks, footer = parse_fix_blocks(text)

    kept: list[list[str]] = []
    pending_call_file: Path | None = None
    accepted_calls = 0
    for block in blocks:
        replacement = replacement_for_block(block)
        if replacement is None:
            pending_call_file = None
            continue

        source_path, offset, length, replacement_text = replacement
        message = block_message(block)
        if length != 0:
            raise BenchmarkError(f"non-insertion replacement is not supported in {fixes_path}")

        if message == "insert _s here" and replacement_text == "_s":
            identifier = identifier_before_offset(source_path, offset)
            if identifier in SEMANTIC_ALLOCATOR_SOURCE_NAMES:
                kept.append(block)
                pending_call_file = source_path
                accepted_calls += 1
            else:
                pending_call_file = None
        elif message == "insert file name, line number, and type" and pending_call_file == source_path:
            kept.append(block)
            pending_call_file = None
        else:
            pending_call_file = None

    if not kept:
        raise BenchmarkError(f"no Valkey semantic allocator replacements found in {fixes_path}")

    filtered_lines = header if header else ["Diagnostics:"]
    filtered_lines.extend(line for block in kept for line in block)
    filtered_lines.extend(footer)
    fixes_path.write_text("\n".join(filtered_lines) + "\n", encoding="utf-8")
    return accepted_calls


def insert_before_final_endif(path: Path, marker: str, insertion: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    idx = text.rfind("\n#endif")
    if idx == -1:
        raise BenchmarkError(f"could not find final #endif in {path}")
    path.write_text(text[:idx] + "\n\n" + insertion.rstrip() + "\n" + text[idx:], encoding="utf-8")


def patch_valkey_semantic_allocators(work_valkey: Path) -> None:
    zblock = r"""
/* HeapLENS semantic logging for Valkey allocator call sites. */
#ifdef HEAPLENS_VALKEY_SEMANTIC_ALLOC
#include <stdint.h>
#include <string.h>

void memhook_record_alloc(void *ptr, size_t size, int line, uint16_t fid, uint16_t tid);
void memhook_record_free(void *ptr);

static inline size_t heaplens_valkey_record_size(size_t requested, const size_t *usable) {
    return (usable && *usable) ? *usable : requested;
}

static inline void *heaplens_valkey_record_alloc(void *ptr, size_t size, int line, uint16_t fid, uint16_t tid) {
    if (ptr) memhook_record_alloc(ptr, size, line, fid, tid);
    return ptr;
}

static inline void *heaplens_valkey_record_realloc(void *oldptr, void *newptr, size_t size,
                                                   int line, uint16_t fid, uint16_t tid) {
    if (oldptr && (newptr || size == 0)) memhook_record_free(oldptr);
    if (newptr) memhook_record_alloc(newptr, size, line, fid, tid);
    return newptr;
}

static inline void *zmalloc_s(size_t size, int line, uint16_t fid, uint16_t tid) {
    return heaplens_valkey_record_alloc(valkey_malloc(size), size, line, fid, tid);
}

static inline void *zmalloc_cache_aligned_s(size_t size, int line, uint16_t fid, uint16_t tid) {
    return heaplens_valkey_record_alloc(valkey_malloc_cache_aligned(size), size, line, fid, tid);
}

static inline void *zcalloc_s(size_t size, int line, uint16_t fid, uint16_t tid) {
    return heaplens_valkey_record_alloc(valkey_calloc(size), size, line, fid, tid);
}

static inline void *zcalloc_num_s(size_t num, size_t size, int line, uint16_t fid, uint16_t tid) {
    return heaplens_valkey_record_alloc(zcalloc_num(num, size), num * size, line, fid, tid);
}

static inline void *ztrymalloc_s(size_t size, int line, uint16_t fid, uint16_t tid) {
    return heaplens_valkey_record_alloc(ztrymalloc(size), size, line, fid, tid);
}

static inline void *ztrycalloc_s(size_t size, int line, uint16_t fid, uint16_t tid) {
    return heaplens_valkey_record_alloc(ztrycalloc(size), size, line, fid, tid);
}

static inline void *zmalloc_usable_s(size_t size, size_t *usable, int line, uint16_t fid, uint16_t tid) {
    void *ptr = zmalloc_usable(size, usable);
    return heaplens_valkey_record_alloc(ptr, heaplens_valkey_record_size(size, usable), line, fid, tid);
}

static inline void *zcalloc_usable_s(size_t size, size_t *usable, int line, uint16_t fid, uint16_t tid) {
    void *ptr = zcalloc_usable(size, usable);
    return heaplens_valkey_record_alloc(ptr, heaplens_valkey_record_size(size, usable), line, fid, tid);
}

static inline void *ztrymalloc_usable_s(size_t size, size_t *usable, int line, uint16_t fid, uint16_t tid) {
    void *ptr = ztrymalloc_usable(size, usable);
    return heaplens_valkey_record_alloc(ptr, heaplens_valkey_record_size(size, usable), line, fid, tid);
}

static inline void *ztrycalloc_usable_s(size_t size, size_t *usable, int line, uint16_t fid, uint16_t tid) {
    void *ptr = ztrycalloc_usable(size, usable);
    return heaplens_valkey_record_alloc(ptr, heaplens_valkey_record_size(size, usable), line, fid, tid);
}

static inline void *zrealloc_s(void *ptr, size_t size, int line, uint16_t fid, uint16_t tid) {
    void *newptr = valkey_realloc(ptr, size);
    return heaplens_valkey_record_realloc(ptr, newptr, size, line, fid, tid);
}

static inline void *ztryrealloc_s(void *ptr, size_t size, int line, uint16_t fid, uint16_t tid) {
    void *newptr = ztryrealloc(ptr, size);
    return heaplens_valkey_record_realloc(ptr, newptr, size, line, fid, tid);
}

static inline void *zrealloc_usable_s(void *ptr, size_t size, size_t *usable, int line, uint16_t fid, uint16_t tid) {
    void *newptr = zrealloc_usable(ptr, size, usable);
    return heaplens_valkey_record_realloc(ptr, newptr, heaplens_valkey_record_size(size, usable), line, fid, tid);
}

static inline void *ztryrealloc_usable_s(void *ptr, size_t size, size_t *usable, int line, uint16_t fid, uint16_t tid) {
    void *newptr = ztryrealloc_usable(ptr, size, usable);
    return heaplens_valkey_record_realloc(ptr, newptr, heaplens_valkey_record_size(size, usable), line, fid, tid);
}

static inline char *zstrdup_s(const char *s, int line, uint16_t fid, uint16_t tid) {
    char *ptr = zstrdup(s);
    return (char *)heaplens_valkey_record_alloc(ptr, s ? strlen(s) + 1 : 0, line, fid, tid);
}
#endif
"""
    sds_block = r"""
/* HeapLENS semantic logging aliases for SDS allocator macros. */
#ifdef HEAPLENS_VALKEY_SEMANTIC_ALLOC
#define s_malloc_s zmalloc_s
#define s_realloc_s zrealloc_s
#define s_trymalloc_s ztrymalloc_s
#define s_tryrealloc_s ztryrealloc_s
#define s_malloc_usable_s zmalloc_usable_s
#define s_realloc_usable_s zrealloc_usable_s
#define s_trymalloc_usable_s ztrymalloc_usable_s
#define s_tryrealloc_usable_s ztryrealloc_usable_s
#endif
"""
    listpack_block = r"""
/* HeapLENS semantic logging aliases for listpack allocator macros. */
#ifdef HEAPLENS_VALKEY_SEMANTIC_ALLOC
#define lp_malloc_s(sz, line, fid, tid) zmalloc_usable_s((sz), NULL, (line), (fid), (tid))
#define lp_realloc_s(ptr, sz, line, fid, tid) zrealloc_usable_s((ptr), (sz), NULL, (line), (fid), (tid))
#endif
"""
    rax_block = r"""
/* HeapLENS semantic logging aliases for rax allocator macros. */
#ifdef HEAPLENS_VALKEY_SEMANTIC_ALLOC
#define rax_malloc_s zmalloc_s
#define rax_realloc_s zrealloc_s
#endif
"""
    insert_before_final_endif(work_valkey / "src" / "zmalloc.h", "HEAPLENS semantic logging for Valkey", zblock)
    insert_before_final_endif(work_valkey / "src" / "sdsalloc.h", "HEAPLENS semantic logging aliases for SDS", sds_block)
    insert_before_final_endif(work_valkey / "src" / "listpack_malloc.h", "HEAPLENS semantic logging aliases for listpack", listpack_block)
    insert_before_final_endif(work_valkey / "src" / "rax_malloc.h", "HEAPLENS semantic logging aliases for rax", rax_block)


def apply_filtered_replacements(fixes_path: Path, log_path: Path) -> None:
    _, blocks, _ = parse_fix_blocks(fixes_path.read_text(encoding="utf-8"))
    replacements_by_file: dict[Path, list[tuple[int, str]]] = {}

    for block in blocks:
        replacement = replacement_for_block(block)
        if replacement is None:
            continue
        source_path, offset, length, replacement_text = replacement
        if length != 0:
            raise BenchmarkError(f"non-insertion replacement is not supported in {fixes_path}")
        replacements_by_file.setdefault(source_path, []).append((offset, replacement_text))

    if not replacements_by_file:
        raise BenchmarkError(f"no replacements found in {fixes_path}")

    applied: list[str] = []
    for source_path, replacements in sorted(replacements_by_file.items()):
        text = source_path.read_text(encoding="utf-8")
        for offset, replacement in sorted(replacements, reverse=True):
            if offset < 0 or offset > len(text):
                raise BenchmarkError(f"replacement offset {offset} is outside {source_path}")
            text = text[:offset] + replacement + text[offset:]
        source_path.write_text(text, encoding="utf-8")
        applied.append(f"{source_path}: {len(replacements)}")

    log_path.write_text(
        "Applied filtered semantic allocator insertion replacements:\n"
        + "\n".join(applied)
        + "\n",
        encoding="utf-8",
    )


def patch_valkey_makefile_for_memhook(work_valkey: Path) -> None:
    makefile = work_valkey / "src" / "Makefile"
    marker = "# HeapLENS benchmark memhook link flags"
    text = makefile.read_text(encoding="utf-8")
    if marker in text:
        return
    text = text.rstrip() + f"\n\n{marker}\nFINAL_LIBS += {MEMHOOK_LIBS}\n"
    makefile.write_text(text + "\n", encoding="utf-8")


def instrument_valkey(
    source_dir: Path,
    instrumented_dir: Path,
    run_dir: Path,
    jobs: str,
    malloc_backend: str,
) -> None:
    clean_source = run_dir / "work" / "valkey_source"
    copy_clean_valkey(source_dir, clean_source)
    build_helper = write_compile_commands_helper(run_dir, jobs, malloc_backend)

    buildcmd = shlex.join(["bash", str(build_helper)])
    print("==> Running Sifter instrumentation")
    run_stream(
        [
            str(CONTAINER_SIFTER_ROOT / "sifter.sh"),
            str(clean_source),
            str(instrumented_dir),
            "--skip-refactor",
            "-b",
            buildcmd,
        ],
        run_dir / "sifter_instrumentation.log",
        cwd=CONTAINER_SIFTER_ROOT,
        echo=False,
    )

    accepted_calls = filter_fixes_to_semantic_allocators(
        instrumented_dir / "fixes.yaml", run_dir / "fixes_unfiltered.yaml"
    )
    (run_dir / "semantic_allocators.txt").write_text(
        "\n".join(sorted(SEMANTIC_ALLOCATOR_SOURCE_NAMES)) + "\n",
        encoding="utf-8",
    )
    (run_dir / "semantic_allocator_replacements.txt").write_text(
        f"accepted_allocator_calls={accepted_calls}\n",
        encoding="utf-8",
    )

    print("==> Applying filtered Sifter replacements")
    apply_filtered_replacements(
        instrumented_dir / "fixes.yaml",
        run_dir / "apply_replacements.log",
    )

    print("==> Adding Valkey semantic allocator logging shims")
    patch_valkey_semantic_allocators(instrumented_dir)
    if __package__:
        from .valkey_terminal import patch_source
    else:
        from valkey_terminal import patch_source
    patch_source(instrumented_dir)

    for name in ("compile_commands.json", "fielddump.txt", "fileset_dump.txt", "typeset_dump.txt", "fixes.yaml"):
        copy_if_exists(instrumented_dir / name, run_dir / name)

    for required in ("fileset_dump.txt", "typeset_dump.txt"):
        if not (run_dir / required).exists():
            raise BenchmarkError(f"Sifter did not produce {required}; see {run_dir / 'sifter_instrumentation.log'}")


def append_command_output(log_path: Path, label: str, proc: subprocess.CompletedProcess[str]) -> None:
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n$ {label}\n")
        log.write(proc.stdout)
        log.write(f"\nexit_code={proc.returncode}\n")


def clean_instrumented_build(work_valkey: Path, build_log: Path) -> None:
    build_log.parent.mkdir(parents=True, exist_ok=True)
    build_log.write_text("", encoding="utf-8")
    distclean = run(["make", "distclean"], cwd=work_valkey, check=False)
    append_command_output(build_log, "make distclean", distclean)
    if distclean.returncode != 0:
        clean = run(["make", "clean"], cwd=work_valkey, check=False)
        append_command_output(build_log, "make clean", clean)


def build_instrumented_valkey(work_valkey: Path, build_log: Path, jobs: str, malloc_backend: str) -> None:
    print("==> Rebuilding instrumented Valkey against memhook")
    clean_instrumented_build(work_valkey, build_log)
    patch_valkey_makefile_for_memhook(work_valkey)
    run_stream(
        valkey_make_cmd(jobs, with_memhook=True, malloc_backend=malloc_backend),
        build_log,
        cwd=work_valkey,
        echo=False,
        mode="a",
    )


def build_baseline_valkey(
    source_dir: Path,
    baseline_dir: Path,
    build_log: Path,
    jobs: str,
    malloc_backend: str,
) -> None:
    print("==> Building no-HeapLENS Valkey for measured throughput")
    copy_clean_valkey(source_dir, baseline_dir)
    clean_instrumented_build(baseline_dir, build_log)
    jemalloc_dir = baseline_dir / "deps" / "jemalloc"
    if malloc_backend == "jemalloc" and not (jemalloc_dir / "configure").is_file():
        run_stream(["autoconf"], build_log, cwd=jemalloc_dir, echo=False, mode="a")
    run_stream(
        valkey_make_cmd(jobs, with_memhook=False, malloc_backend=malloc_backend),
        build_log,
        cwd=baseline_dir,
        echo=False,
        mode="a",
    )


def runtime_env(dump_file: Path | None) -> dict[str, str]:
    env = os.environ.copy()
    ld_library_path = env.get("LD_LIBRARY_PATH")
    env["LD_LIBRARY_PATH"] = (
        f"/root/sifter/memhook:{ld_library_path}" if ld_library_path else "/root/sifter/memhook"
    )
    if dump_file is not None:
        env["MEMHOOK_OUTPUT_DUMP_FILE"] = str(dump_file)
    return env


def wait_for_server(
    cli: Path,
    port: int,
    server_proc: subprocess.Popen[str],
    server_log: Path,
    cli_env: dict[str, str],
) -> None:
    for _ in range(100):
        if run([str(cli), "-h", "127.0.0.1", "-p", str(port), "ping"], env=cli_env, check=False).returncode == 0:
            return
        if server_proc.poll() is not None:
            raise BenchmarkError(f"Valkey server exited during startup. See {server_log}")
        time.sleep(0.1)
    raise BenchmarkError(f"Valkey server did not become ready on port {port}. See {server_log}")


def finish_trace_producers(port: int, server_proc: subprocess.Popen[str]) -> None:
    """Seal every persistent producer after load; failure forbids conversion."""
    deadline = time.monotonic() + 90
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        stream = sock.makefile("rb")
        while time.monotonic() < deadline:
            if server_proc.poll() is not None:
                raise BenchmarkError("trace server exited before producer finalization")
            sock.settimeout(max(0.1, deadline - time.monotonic()))
            sock.sendall(b"*2\r\n$5\r\nDEBUG\r\n$15\r\nheaplens-finish\r\n")
            reply = stream.readline(4096)
            if reply == b"+OK\r\n":
                return
            if not reply.startswith(b"-ERR HeapLENS producers not quiescent"):
                raise BenchmarkError(f"trace finalization rejected: {reply!r}")
            time.sleep(0.1)
    raise BenchmarkError("trace producer finalization timed out; trace invalid")


def shutdown_server(
    cli: Path,
    port: int,
    server_proc: subprocess.Popen[str] | None,
    cli_env: dict[str, str],
) -> None:
    if server_proc is None or server_proc.poll() is not None:
        return
    run([str(cli), "-h", "127.0.0.1", "-p", str(port), "shutdown", "nosave"], env=cli_env, check=False)
    for _ in range(100):
        if server_proc.poll() is not None:
            return
        time.sleep(0.1)
    server_proc.terminate()
    try:
        server_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server_proc.kill()


def memtier_common(port: int) -> list[str]:
    memtier = executable("memtier_benchmark")
    if memtier is None:
        raise BenchmarkError("memtier_benchmark was not found in PATH")
    return [memtier, "--server=127.0.0.1", f"--port={port}", "--protocol=redis"]


def memtier_preload_args(client_threads: int, json_path: Path) -> list[str]:
    return [
        f"--threads={client_threads}",
        f"--clients={MEMTIER_CLIENTS}",
        f"--pipeline={MEMTIER_PIPELINE}",
        f"--ratio={PRELOAD_RATIO}",
        "--key-pattern=P:P",
        f"--key-prefix={KEY_PREFIX}",
        f"--key-minimum={KEY_MINIMUM}",
        f"--key-maximum={KEY_MAXIMUM}",
        "--requests=allkeys",
        f"--data-size={DATA_SIZE}",
        "--distinct-client-seed",
        "--hide-histogram",
        f"--json-out-file={json_path}",
    ]


def memtier_measured_args(client_threads: int, json_path: Path) -> list[str]:
    return [
        f"--threads={client_threads}",
        f"--clients={MEMTIER_CLIENTS}",
        f"--pipeline={MEMTIER_PIPELINE}",
        f"--ratio={MEASURED_RATIO}",
        "--key-pattern=R:R",
        f"--key-prefix={KEY_PREFIX}",
        f"--key-minimum={KEY_MINIMUM}",
        f"--key-maximum={KEY_MAXIMUM}",
        f"--data-size={DATA_SIZE}",
        f"--test-time={TEST_TIME_SECONDS}",
        "--distinct-client-seed",
        "--hide-histogram",
        f"--json-out-file={json_path}",
    ]


def server_command(
    server: Path,
    run_dir: Path,
    server_log: Path,
    port: int,
    server_threads: int,
    server_cpus: list[int],
    *,
    no_numa_pin: bool,
) -> list[str]:
    return [
        *pin_prefix(server_cpus, SERVER_NUMA_NODE, no_numa_pin=no_numa_pin),
        str(server),
        "--bind",
        "127.0.0.1",
        "--port",
        str(port),
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


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def sqlite_counts(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        return {}
    counts: dict[str, int] = {}
    with sqlite3.connect(db_path) as conn:
        queries = {
            "supertable_rows": "SELECT COUNT(*) FROM SUPERTABLE",
            "distinct_types": "SELECT COUNT(DISTINCT TYPE) FROM SUPERTABLE",
            "field_rows": "SELECT COUNT(*) FROM FIELDS",
            "stats_rows": "SELECT COUNT(*) FROM STATS",
        }
        for key, query in queries.items():
            try:
                counts[key] = int(conn.execute(query).fetchone()[0])
            except sqlite3.Error:
                counts[key] = 0
    return counts


def convert_trace(run_dir: Path, args: argparse.Namespace) -> Path:
    binary_dump = run_dir / "binary_dump.txt"
    type_dump = run_dir / "typeset_dump.txt"
    file_dump = run_dir / "fileset_dump.txt"
    field_dump = run_dir / "fielddump.txt"
    db_path = run_dir / "allocs.sqlite"

    if not binary_dump.exists():
        raise BenchmarkError(f"missing memhook dump: {binary_dump}")
    if file_size(binary_dump) == 0:
        raise BenchmarkError(f"memhook dump is empty: {binary_dump}")
    if not type_dump.exists() or not file_dump.exists():
        raise BenchmarkError("missing Sifter type/file dumps; conversion cannot continue")
    if db_path.exists():
        raise BenchmarkError(f"SQLite output already exists: {db_path}")

    print("==> Building trace converter")
    run_stream(
        ["make", "-C", str(CONTAINER_SIFTER_ROOT / "type_analysis"), "bin/convert_to_db"],
        run_dir / "convert_build.log",
        echo=False,
    )

    cmd = [
        str(CONTAINER_SIFTER_ROOT / "type_analysis" / "bin" / "convert_to_db"),
        "--memory-dump",
        str(binary_dump),
        "--type-dump",
        str(type_dump),
        "--file-dump",
        str(file_dump),
        "--output-db",
        str(db_path),
        "--sample",
        str(args.sample),
        "--num-pages-per-type",
        str(args.pages_per_type),
        "--threads",
        str(args.db_threads),
    ]
    if field_dump.exists():
        cmd.extend(["--field-dump", str(field_dump)])

    print("==> Converting trace to SQLite")
    run_stream(cmd, run_dir / "convert.log")
    return db_path


def link_for_visualization(run_dir: Path, db_path: Path) -> Path | None:
    viz_dir = CONTAINER_SIFTER_ROOT / "sifter_vis_d3"
    if not viz_dir.is_dir() or not db_path.exists():
        return None

    link_path = viz_dir / f"{run_dir.name}.sqlite"
    if link_path.exists() and not link_path.is_symlink():
        return None
    if link_path.is_symlink():
        link_path.unlink()

    target = os.path.relpath(db_path, viz_dir)
    os.symlink(target, link_path)
    return link_path


def write_summary(
    run_dir: Path,
    config: dict[str, Any],
    db_path: Path,
    viz_link: Path | None,
) -> None:
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
    trace = {
        "trace_scope": config.get("trace_scope"),
        "trace_preload_json": str(run_dir / "trace_preload.json"),
        "trace_preload_log": str(run_dir / "trace_preload.log"),
        "binary_dump": str(run_dir / "binary_dump.txt"),
        "binary_dump_bytes": file_size(run_dir / "binary_dump.txt"),
        "sqlite_db": str(db_path),
        "sqlite_db_bytes": file_size(db_path),
        "field_dump": str(run_dir / "fielddump.txt") if (run_dir / "fielddump.txt").exists() else None,
        "file_dump": str(run_dir / "fileset_dump.txt"),
        "type_dump": str(run_dir / "typeset_dump.txt"),
        "viz_link": str(viz_link) if viz_link else None,
        **sqlite_counts(db_path),
    }
    summary = {
        "benchmark": BENCHMARK_ID,
        "mode": "heaplens-trace",
        "config": config,
        "results": results,
        "memory_after": memory,
        "stats_after": stats,
        "trace": trace,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        f"benchmark={BENCHMARK_ID}",
        "mode=heaplens-trace",
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
        f"binary_dump_bytes={trace['binary_dump_bytes']}",
        f"sqlite_db_bytes={trace['sqlite_db_bytes']}",
        f"supertable_rows={trace.get('supertable_rows', '')}",
        f"distinct_types={trace.get('distinct_types', '')}",
        f"field_rows={trace.get('field_rows', '')}",
        f"sqlite_db={db_path}",
    ]
    if viz_link:
        lines.append(f"viz_link={viz_link}")
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
    if not (CONTAINER_SIFTER_ROOT / "sifter.sh").exists():
        raise BenchmarkError(f"Sifter root not found at {CONTAINER_SIFTER_ROOT}")

    run_dir = Path(args.run_dir or default_container_run_dir())
    run_dir.mkdir(parents=True, exist_ok=True)
    instrumented_valkey = run_dir / "work" / "valkey_instrumented"
    baseline_valkey = run_dir / "work" / "valkey_baseline"

    server_cpus = primary_cpus_for_node(SERVER_NUMA_NODE)
    client_cpus = primary_cpus_for_node(CLIENT_NUMA_NODE)
    server_threads = len(server_cpus)
    client_threads = len(client_cpus)
    jobs = make_jobs()

    config: dict[str, Any] = {
        "layout": "cross-node",
        "profile": "large-read-mostly-string-cache-cross-node",
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
        "ratio": MEASURED_RATIO,
        "preload_ratio": PRELOAD_RATIO,
        "key_minimum": KEY_MINIMUM,
        "key_maximum": KEY_MAXIMUM,
        "key_prefix": KEY_PREFIX,
        "data_size": DATA_SIZE,
        "test_time_seconds": TEST_TIME_SECONDS,
        "port": args.port,
        "numa_pin": not args.no_numa_pin,
        "sample": args.sample,
        "pages_per_type": args.pages_per_type,
        "db_threads": args.db_threads,
        "trace_scope": "preload-and-measured" if args.trace_measured else "preload-only",
        "throughput_measurement": "heaplens-instrumented" if args.trace_measured else "no-heaplens-baseline",
        "heaplens_allocator_instrumentation": "valkey-custom-allocator-call-sites",
        "heaplens_semantic_allocator_names": sorted(SEMANTIC_ALLOCATOR_SOURCE_NAMES),
        "valkey_source": str(source_dir),
        "valkey_commit": git_rev(source_dir),
        "sifter_root": str(CONTAINER_SIFTER_ROOT),
    }
    (run_dir / "benchmark_config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    build_log = run_dir / "build.log"
    baseline_build_log = run_dir / "baseline_build.log"
    server_log = run_dir / "server.log"
    baseline_server_log = run_dir / "baseline_server.log"
    trace_preload_log = run_dir / "trace_preload.log"
    baseline_preload_log = run_dir / "baseline_preload.log"
    benchmark_log = run_dir / "benchmark.log"
    trace_preload_json = run_dir / "trace_preload.json"
    baseline_preload_json = run_dir / "baseline_preload.json"
    benchmark_json = run_dir / "benchmark.json"
    memory_after = run_dir / "memory_after.txt"
    stats_after = run_dir / "stats_after.txt"
    trace_memory_after = run_dir / "trace_memory_after_preload.txt"
    trace_stats_after = run_dir / "trace_stats_after_preload.txt"
    binary_dump = run_dir / "binary_dump.txt"
    cli_dump = run_dir / "cli_ignored_binary_dump.txt"

    instrument_valkey(source_dir, instrumented_valkey, run_dir, jobs, args.malloc_backend)
    build_instrumented_valkey(instrumented_valkey, build_log, jobs, args.malloc_backend)

    server = instrumented_valkey / "src" / "valkey-server"
    cli = instrumented_valkey / "src" / "valkey-cli"
    if not server.exists() or not cli.exists():
        raise BenchmarkError(f"instrumented Valkey build did not produce server/cli binaries in {instrumented_valkey / 'src'}")

    server_cmd = server_command(
        server,
        run_dir,
        server_log,
        args.port,
        server_threads,
        server_cpus,
        no_numa_pin=args.no_numa_pin,
    )
    server_cmd += ["--enable-debug-command", "yes"]
    client_prefix = pin_prefix(client_cpus, CLIENT_NUMA_NODE, no_numa_pin=args.no_numa_pin)
    cli_env = runtime_env(cli_dump)
    server_env = runtime_env(binary_dump)

    print(
        "==> Fixed profile: cross-node "
        f"server_node={SERVER_NUMA_NODE} server_cpus={config['server_cpus']} "
        f"client_node={CLIENT_NUMA_NODE} client_cpus={config['client_cpus']}"
    )
    print(f"==> Starting instrumented Valkey server on port {args.port}")
    server_proc: subprocess.Popen[str] | None = None
    try:
        server_proc = subprocess.Popen(server_cmd, env=server_env, text=True)
        wait_for_server(cli, args.port, server_proc, server_log, cli_env)

        common = memtier_common(args.port)
        print("==> Running traced memtier preload")
        run_stream(
            [*client_prefix, *common, *memtier_preload_args(client_threads, trace_preload_json)],
            trace_preload_log,
        )

        trace_memory_after.write_text(
            run([str(cli), "-h", "127.0.0.1", "-p", str(args.port), "info", "memory"], env=cli_env, check=False).stdout,
            encoding="utf-8",
        )
        trace_stats_after.write_text(
            run([str(cli), "-h", "127.0.0.1", "-p", str(args.port), "info", "stats"], env=cli_env, check=False).stdout,
            encoding="utf-8",
        )

        if args.trace_measured:
            print("==> Running measured memtier benchmark with memhook logging enabled")
            run_stream(
                [*client_prefix, *common, *memtier_measured_args(client_threads, benchmark_json)],
                benchmark_log,
            )

            print("==> Capturing INFO memory/stats")
            memory_after.write_text(
                run([str(cli), "-h", "127.0.0.1", "-p", str(args.port), "info", "memory"], env=cli_env, check=False).stdout,
                encoding="utf-8",
            )
            stats_after.write_text(
                run([str(cli), "-h", "127.0.0.1", "-p", str(args.port), "info", "stats"], env=cli_env, check=False).stdout,
                encoding="utf-8",
            )
        finish_trace_producers(args.port, server_proc)
    finally:
        print("==> Shutting down instrumented Valkey")
        shutdown_server(cli, args.port, server_proc, cli_env)

    if server_proc.returncode != 0:
        raise BenchmarkError("trace server did not exit successfully; refusing conversion")
    db_path = convert_trace(run_dir, args)
    viz_link = link_for_visualization(run_dir, db_path)

    if not args.trace_measured:
        build_baseline_valkey(source_dir, baseline_valkey, baseline_build_log, jobs, args.malloc_backend)
        baseline_server = baseline_valkey / "src" / "valkey-server"
        baseline_cli = baseline_valkey / "src" / "valkey-cli"
        if not baseline_server.exists() or not baseline_cli.exists():
            raise BenchmarkError(f"baseline Valkey build did not produce server/cli binaries in {baseline_valkey / 'src'}")

        baseline_cmd = server_command(
            baseline_server,
            run_dir,
            baseline_server_log,
            args.port,
            server_threads,
            server_cpus,
            no_numa_pin=args.no_numa_pin,
        )
        baseline_env = os.environ.copy()
        baseline_proc: subprocess.Popen[str] | None = None
        try:
            print(f"==> Starting no-HeapLENS Valkey server on port {args.port}")
            baseline_proc = subprocess.Popen(baseline_cmd, env=baseline_env, text=True)
            wait_for_server(baseline_cli, args.port, baseline_proc, baseline_server_log, baseline_env)

            common = memtier_common(args.port)
            print("==> Running baseline memtier preload")
            run_stream(
                [*client_prefix, *common, *memtier_preload_args(client_threads, baseline_preload_json)],
                baseline_preload_log,
            )

            print("==> Running measured memtier benchmark")
            run_stream(
                [*client_prefix, *common, *memtier_measured_args(client_threads, benchmark_json)],
                benchmark_log,
            )

            print("==> Capturing INFO memory/stats")
            memory_after.write_text(
                run([str(baseline_cli), "-h", "127.0.0.1", "-p", str(args.port), "info", "memory"], env=baseline_env, check=False).stdout,
                encoding="utf-8",
            )
            stats_after.write_text(
                run([str(baseline_cli), "-h", "127.0.0.1", "-p", str(args.port), "info", "stats"], env=baseline_env, check=False).stdout,
                encoding="utf-8",
            )
        finally:
            print("==> Shutting down no-HeapLENS Valkey")
            shutdown_server(baseline_cli, args.port, baseline_proc, baseline_env)

    write_summary(run_dir, config, db_path, viz_link)
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
