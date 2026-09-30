#!/usr/bin/env python3
"""Unified HeapLENS page snapshot export pipeline.

This script intentionally reuses the visualization backend Sampler for page
selection and clustering. It writes a richer v2 raw text dump, compact v2 files
for LLM prompts, and a workload-agnostic analysis report from one shared object
model.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import math
import sqlite3
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sampler import Sampler


SNAPSHOT_INTERVALS = 8
DEFAULT_PAGE_SIZE = 4096
DEFAULT_CACHE_LINE_SIZE = 64
DEFAULT_ADJACENT_WINDOW = 128
DEFAULT_L1_SETS = 64


@dataclasses.dataclass(frozen=True)
class FieldMember:
    name: str
    subtype: str
    offset: int
    size: int


@dataclasses.dataclass(frozen=True)
class ContainerStats:
    child_allocs: int = 0
    child_bytes: int = 0
    child_types: tuple[str, ...] = ()
    source: str = "none"


@dataclasses.dataclass(frozen=True)
class Obj:
    page_addr: int
    cluster: int
    offset: int
    cache_line: int
    l1_index: int
    align_bucket: str
    size: int
    actual_size: int
    addr: int
    actual_addr: int
    split_offset: int
    split_kind: str
    alias: str
    type_name: str
    alloc_ts: int
    free_ts: int | None
    is_container: bool
    contained_allocs: int
    contained_bytes: int
    child_type_aliases: tuple[str, ...]
    container_source: str

    def first_line(self, cache_line_size: int) -> int:
        return self.offset // cache_line_size

    def last_line(self, cache_line_size: int) -> int:
        if self.size <= 0:
            return self.first_line(cache_line_size)
        return (self.offset + self.size - 1) // cache_line_size

    def ideal_lines(self, cache_line_size: int) -> int:
        return max(1, math.ceil(self.size / cache_line_size))

    def extra_lines(self, cache_line_size: int) -> int:
        return (
            self.last_line(cache_line_size)
            - self.first_line(cache_line_size)
            + 1
            - self.ideal_lines(cache_line_size)
        )

    def lines(self, cache_line_size: int) -> range:
        return range(self.first_line(cache_line_size), self.last_line(cache_line_size) + 1)

    def windows(self, window_size: int) -> range:
        first = self.offset // window_size
        last = (self.offset + max(self.size, 1) - 1) // window_size
        return range(first, last + 1)


@dataclasses.dataclass
class Snapshot:
    index: int
    time: int
    pages: dict[int, list[Obj]]


@dataclasses.dataclass
class ExportModel:
    db: Path
    generated_at: str
    page_size: int
    cache_line_size: int
    adjacent_window: int
    l1_sets: int
    type_names: list[str]
    aliases: dict[str, str]
    fields: dict[str, list[FieldMember]]
    clusters: dict[int, dict[str, object]]
    page_clusters: dict[int, int]
    snapshots: list[Snapshot]
    selected_pages: int
    clustered_pages: int
    num_clusters: int


def alias_for_index(index: int) -> str:
    alphabet = string.ascii_uppercase
    base = len(alphabet)
    index += 1
    parts: list[str] = []
    while index:
        index -= 1
        parts.append(alphabet[index % base])
        index //= base
    return "".join(reversed(parts))


def alignment_bucket(addr: int) -> str:
    for bucket in (64, 48, 32, 16, 8):
        if addr % bucket == 0:
            return str(bucket)
    return "other"


def table_columns(db_path: Path, table: str) -> set[str]:
    with sqlite3.connect(db_path) as con:
        rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def table_exists(db_path: Path, table: str) -> bool:
    with sqlite3.connect(db_path) as con:
        row = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name=?",
            (table,),
        ).fetchone()
    return row is not None


def load_actual_sizes(db_path: Path) -> dict[tuple[str, int, int], int]:
    cols = table_columns(db_path, "SUPERTABLE")
    if "ACTUALSIZE" in cols:
        query = """
            SELECT TYPE, ACTUALADDR, TIMESTAMP, MAX(ACTUALSIZE)
            FROM SUPERTABLE
            WHERE isNew=1 AND TYPE IS NOT NULL AND TYPE != 'NULL'
            GROUP BY TYPE, ACTUALADDR, TIMESTAMP
        """
    else:
        query = """
            SELECT TYPE, ACTUALADDR, TIMESTAMP, SUM(SIZE)
            FROM SUPERTABLE
            WHERE isNew=1 AND TYPE IS NOT NULL AND TYPE != 'NULL'
            GROUP BY TYPE, ACTUALADDR, TIMESTAMP
        """

    sizes: dict[tuple[str, int, int], int] = {}
    with sqlite3.connect(db_path) as con:
        for type_name, actual_addr, timestamp, size in con.execute(query):
            if type_name is None or actual_addr is None or timestamp is None or size is None:
                continue
            sizes[(str(type_name), int(actual_addr), int(timestamp))] = int(size)
    return sizes


def load_container_stats(db_path: Path) -> dict[tuple[str, int, int, int], ContainerStats]:
    if not table_exists(db_path, "CONTAINERS"):
        return {}

    stats: dict[tuple[str, int, int, int], ContainerStats] = {}
    query = """
        SELECT TYPE, ADDRESS, TIMESTAMP, SIZE, CHILD_ALLOCS, CHILD_BYTES, CHILD_TYPES
        FROM CONTAINERS
    """
    with sqlite3.connect(db_path) as con:
        for row in con.execute(query):
            type_name, address, timestamp, size, child_allocs, child_bytes, child_types = row
            child_type_tuple = tuple(
                tp for tp in str(child_types or "").split(";") if tp
            )
            stats[(str(type_name), int(address), int(timestamp), int(size))] = ContainerStats(
                child_allocs=int(child_allocs),
                child_bytes=int(child_bytes),
                child_types=child_type_tuple,
                source="db",
            )
    return stats


def normalize_fields(fields_data: dict[str, list[dict[str, object]]]) -> dict[str, list[FieldMember]]:
    fields: dict[str, list[FieldMember]] = {}
    for type_name, entries in fields_data.items():
        fields[type_name] = sorted(
            [
                FieldMember(
                    name=str(entry["name"]),
                    subtype=str(entry["subtype"]),
                    offset=int(entry["offset"]),
                    size=int(entry["size"]),
                )
                for entry in entries
            ],
            key=lambda field: (field.offset, field.name),
        )
    return fields


def field_entries_for_type(fields: dict[str, list[FieldMember]], type_name: str) -> list[FieldMember]:
    return fields.get(type_name, fields.get(type_name.replace(" ", ""), []))


def snapshot_times(pages: dict[str, dict[str, object]]) -> list[int]:
    events = [
        event
        for page in pages.values()
        for event in page.get("events", [])
        if event.get("allocTs") is not None
    ]
    if not events:
        return [0]

    min_ts = int(min(event["allocTs"] for event in events))
    max_ts = int(max(event["allocTs"] for event in events))
    step = (max_ts - min_ts) / SNAPSHOT_INTERVALS
    return [int(round(min_ts + step * i)) for i in range(SNAPSHOT_INTERVALS + 1)]


def object_key(type_name: str, actual_addr: int, alloc_ts: int, actual_size: int) -> tuple[str, int, int, int]:
    return (type_name, actual_addr, alloc_ts, actual_size)


def event_actual_addr(event: dict[str, object]) -> int:
    value = event.get("actualAddr")
    if value is None or (isinstance(value, float) and math.isnan(value)):
        value = event["addr"]
    return int(value)


def event_free_ts(event: dict[str, object]) -> int | None:
    value = event.get("freeTs")
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return int(value)


def split_kind(addr: int, size: int, actual_addr: int, actual_size: int) -> str:
    if actual_size <= 0:
        return "unknown"
    split_offset = addr - actual_addr
    if split_offset == 0 and size == actual_size:
        return "whole"
    if split_offset == 0:
        return "first"
    if split_offset + size >= actual_size:
        return "last"
    return "middle"


def infer_container_stats(base_objects: dict[tuple[str, int, int, int], dict[str, object]]) -> dict[tuple[str, int, int, int], ContainerStats]:
    entries = sorted(
        base_objects.items(),
        key=lambda item: (int(item[1]["actual_addr"]), -int(item[1]["actual_size"])),
    )
    mutable: dict[tuple[str, int, int, int], dict[str, object]] = collections.defaultdict(
        lambda: {"child_allocs": 0, "child_bytes": 0, "child_types": set()}
    )

    for idx, (parent_key, parent) in enumerate(entries):
        parent_start = int(parent["actual_addr"])
        parent_size = int(parent["actual_size"])
        parent_end = parent_start + parent_size
        if parent_size <= 0:
            continue
        parent_alloc = int(parent["alloc_ts"])
        parent_free = parent["free_ts"]

        for child_key, child in entries[idx + 1 :]:
            child_start = int(child["actual_addr"])
            if child_start >= parent_end:
                break
            if child_key == parent_key:
                continue

            child_size = int(child["actual_size"])
            child_end = child_start + child_size
            contains = (
                (parent_start <= child_start and parent_end > child_end)
                or (parent_start < child_start and parent_end >= child_end)
            )
            if not contains:
                continue

            child_alloc = int(child["alloc_ts"])
            if child_alloc < parent_alloc:
                continue
            if parent_free is not None and child_alloc > int(parent_free):
                continue

            mutable[parent_key]["child_allocs"] = int(mutable[parent_key]["child_allocs"]) + 1
            mutable[parent_key]["child_bytes"] = int(mutable[parent_key]["child_bytes"]) + child_size
            mutable[parent_key]["child_types"].add(str(child["type_name"]))

    return {
        key: ContainerStats(
            child_allocs=int(value["child_allocs"]),
            child_bytes=int(value["child_bytes"]),
            child_types=tuple(sorted(value["child_types"])),
            source="inferred",
        )
        for key, value in mutable.items()
        if int(value["child_allocs"]) > 0
    }


def build_model(args: argparse.Namespace) -> ExportModel:
    sampler = Sampler(
        str(args.db),
        page_size=args.page_size,
        cache_line_size=args.cache_line_size,
        num_buckets=args.num_buckets,
    )
    type_names = sorted(sampler.types())
    aliases = {type_name: alias_for_index(idx) for idx, type_name in enumerate(type_names)}
    type_visibility = {type_name: True for type_name in type_names}
    lines_and_stats = sampler.get_all_lines_and_stats()
    pages_data = sampler.get_sample_of_pages(
        -1,
        -1,
        type_visibility,
        args.cluster_alg,
        args.max_run_length,
        args.max_runs_per_cluster,
    )

    fields = normalize_fields(lines_and_stats["fields"])
    actual_sizes = load_actual_sizes(args.db)
    db_containers = load_container_stats(args.db)

    base_objects: dict[tuple[str, int, int, int], dict[str, object]] = {}
    for page in pages_data["page_num_events"].values():
        for event in page.get("events", []):
            if event.get("allocTs") is None or event.get("type") is None:
                continue
            type_name = str(event.get("type") or "UNKNOWN")
            addr = int(event["addr"])
            actual_addr = event_actual_addr(event)
            alloc_ts = int(event["allocTs"])
            actual_size = actual_sizes.get(
                (type_name, actual_addr, alloc_ts),
                int(event["size"]),
            )
            key = object_key(type_name, actual_addr, alloc_ts, actual_size)
            base_objects.setdefault(
                key,
                {
                    "type_name": type_name,
                    "actual_addr": actual_addr,
                    "actual_size": actual_size,
                    "alloc_ts": alloc_ts,
                    "free_ts": event_free_ts(event),
                    "addr": addr,
                },
            )

    inferred_containers = infer_container_stats(base_objects)

    def container_for(key: tuple[str, int, int, int]) -> ContainerStats:
        return db_containers.get(key, inferred_containers.get(key, ContainerStats()))

    times = snapshot_times(pages_data["page_num_events"])
    snapshots: list[Snapshot] = []
    page_addrs = sorted(int(addr) for addr in pages_data["page_num_events"])
    page_clusters = {
        int(page_addr): int(page["cluster"])
        for page_addr, page in pages_data["page_num_events"].items()
    }
    for index, ts in enumerate(times):
        snapshot_pages: dict[int, list[Obj]] = {}
        for page_addr in page_addrs:
            page = pages_data["page_num_events"][str(page_addr)]
            cluster = int(page["cluster"])
            visible: list[Obj] = []
            for event in page.get("events", []):
                if event.get("allocTs") is None:
                    continue
                alloc_ts = int(event["allocTs"])
                free_ts = event_free_ts(event)
                if alloc_ts > ts or (free_ts is not None and free_ts < ts):
                    continue

                type_name = str(event.get("type") or "UNKNOWN")
                alias = aliases.setdefault(type_name, alias_for_index(len(aliases)))
                addr = int(event["addr"])
                actual_addr = event_actual_addr(event)
                size = int(event["size"])
                actual_size = actual_sizes.get((type_name, actual_addr, alloc_ts), size)
                key = object_key(type_name, actual_addr, alloc_ts, actual_size)
                container = container_for(key)
                child_aliases = tuple(
                    aliases.setdefault(child_type, alias_for_index(len(aliases)))
                    for child_type in container.child_types
                )
                offset = addr - page_addr
                visible.append(
                    Obj(
                        page_addr=page_addr,
                        cluster=cluster,
                        offset=offset,
                        cache_line=offset // args.cache_line_size,
                        l1_index=(addr // args.cache_line_size) % args.l1_sets,
                        align_bucket=alignment_bucket(addr),
                        size=size,
                        actual_size=actual_size,
                        addr=addr,
                        actual_addr=actual_addr,
                        split_offset=addr - actual_addr,
                        split_kind=split_kind(addr, size, actual_addr, actual_size),
                        alias=alias,
                        type_name=type_name,
                        alloc_ts=alloc_ts,
                        free_ts=free_ts,
                        is_container=container.child_allocs > 0,
                        contained_allocs=container.child_allocs,
                        contained_bytes=container.child_bytes,
                        child_type_aliases=child_aliases,
                        container_source=container.source,
                    )
                )
            snapshot_pages[page_addr] = visible
        snapshots.append(Snapshot(index=index, time=ts, pages=snapshot_pages))

    generated_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    return ExportModel(
        db=args.db,
        generated_at=generated_at,
        page_size=args.page_size,
        cache_line_size=args.cache_line_size,
        adjacent_window=args.adjacent_window,
        l1_sets=args.l1_sets,
        type_names=list(aliases.keys()),
        aliases=aliases,
        fields=fields,
        clusters=pages_data["clusters"],
        page_clusters=page_clusters,
        snapshots=snapshots,
        selected_pages=len(pages_data["page_num_events"]),
        clustered_pages=int(pages_data["sum_cluster_sizes"]),
        num_clusters=int(pages_data["num_clusters"]),
    )


def format_list(items: Iterable[str]) -> str:
    values = list(items)
    return "[" + ", ".join(values) + "]" if values else "[]"


def write_raw_v2(model: ExportModel, path: Path) -> None:
    lines: list[str] = []
    lines.append("HEAPLENS_PAGE_SNAPSHOTS_V2")
    lines.append(f"GENERATED_AT: {model.generated_at}")
    lines.append(f"SOURCE_DB: {model.db}")
    lines.append(f"SNAPSHOT_INTERVALS: {len(model.snapshots) - 1}")
    lines.append(f"PAGE_SIZE: {model.page_size}")
    lines.append(f"CACHE_LINE_SIZE: {model.cache_line_size}")
    lines.append(f"ADJACENT_LINE_WINDOW: {model.adjacent_window}")
    lines.append(f"L1_SETS: {model.l1_sets}")
    lines.append(f"TOTAL_TYPES: {len(model.type_names)}")
    lines.append(f"TOTAL_PAGES: {model.selected_pages}")
    lines.append(f"CLUSTERED_PAGES: {model.clustered_pages}")
    lines.append(f"NUM_CLUSTERS: {model.num_clusters}")
    lines.append("")
    lines.append("TYPES:")
    for type_name in model.type_names:
        lines.append(f"- alias: {model.aliases[type_name]}")
        lines.append(f"  type: {type_name}")
    lines.append("")
    lines.append("FIELDS:")
    wrote_field = False
    for type_name in model.type_names:
        members = field_entries_for_type(model.fields, type_name)
        if not members:
            continue
        wrote_field = True
        lines.append(f"- alias: {model.aliases[type_name]}")
        lines.append(f"  type: {type_name}")
        lines.append("  members:")
        for member in members:
            lines.append(f"    - name: {member.name}")
            lines.append(f"      subtype: {member.subtype}")
            lines.append(f"      offset: {member.offset}")
            lines.append(f"      size: {member.size}")
    if not wrote_field:
        lines.append("  NONE")
    lines.append("")
    lines.append("CLUSTERS:")
    for cluster_id in sorted(int(key) for key in model.clusters):
        cluster = model.clusters[cluster_id]
        pages = cluster.get("pages", [])
        page_list = list(pages.values()) if isinstance(pages, dict) else list(pages)
        lines.append(f"- cluster_id: {cluster_id}")
        lines.append(f"  size: {cluster['size']}")
        lines.append(f"  page_count: {len(page_list)}")
        lines.append(f"  pages: [{', '.join(str(page) for page in page_list)}]")
    lines.append("")
    lines.append("SNAPSHOTS:")
    for snapshot in model.snapshots:
        lines.append(f"- snapshot_index: {snapshot.index}")
        lines.append(f"  time: {snapshot.time}")
        lines.append("  pages:")
        for page_addr in sorted(snapshot.pages):
            objects = snapshot.pages[page_addr]
            cluster = model.page_clusters.get(page_addr, objects[0].cluster if objects else -1)
            lines.append(f"  - page_addr: {page_addr}")
            lines.append(f"    cluster: {cluster}")
            lines.append(f"    object_count: {len(objects)}")
            if not objects:
                lines.append("    objects: []")
                continue
            lines.append("    objects:")
            for obj in objects:
                lines.append("      -")
                lines.append(f"        alias: {obj.alias}")
                lines.append(f"        type: {obj.type_name}")
                lines.append(f"        size: {obj.size}")
                lines.append(f"        actual_size: {obj.actual_size}")
                lines.append(f"        addr: {obj.addr}")
                lines.append(f"        actual_addr: {obj.actual_addr}")
                lines.append(f"        offset: {obj.offset}")
                lines.append(f"        split_offset: {obj.split_offset}")
                lines.append(f"        split_kind: {obj.split_kind}")
                lines.append(f"        cache_line: {obj.cache_line}")
                lines.append(f"        l1_index: {obj.l1_index}")
                lines.append(f"        align_bucket: {obj.align_bucket}")
                lines.append(f"        is_container: {str(obj.is_container).lower()}")
                lines.append(f"        contained_allocs: {obj.contained_allocs}")
                lines.append(f"        contained_bytes: {obj.contained_bytes}")
                lines.append(f"        child_types: {format_list(obj.child_type_aliases)}")
                lines.append(f"        container_source: {obj.container_source}")
    path.write_text("\n".join(lines) + "\n")


def compact_snapshot_pages(snapshot: Snapshot, pages_per_cluster: int) -> dict[int, list[tuple[int, list[Obj]]]]:
    clusters: dict[int, list[tuple[int, list[Obj]]]] = collections.defaultdict(list)
    for page_addr in sorted(snapshot.pages):
        objects = snapshot.pages[page_addr]
        if not objects:
            continue
        cluster = objects[0].cluster
        if len(clusters[cluster]) < pages_per_cluster:
            clusters[cluster].append((page_addr, objects))
    return dict(clusters)


def write_compact_v2(model: ExportModel, out_dir: Path, pages_per_cluster: int) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    types_path = out_dir / "heaplens_types.txt"
    with types_path.open("w", encoding="utf-8", newline="\n") as out:
        out.write("# heaplens type lookup v2\n")
        out.write("# alias, type\n")
        for type_name in model.type_names:
            out.write(f"{model.aliases[type_name]}, {type_name}\n")
    paths.append(types_path)

    fields_path = out_dir / "heaplens_fields.txt"
    with fields_path.open("w", encoding="utf-8", newline="\n") as out:
        out.write("# heaplens field lookup v2\n")
        out.write("# alias, offset, size, name, subtype\n")
        for type_name in model.type_names:
            for member in field_entries_for_type(model.fields, type_name):
                out.write(
                    f"{model.aliases[type_name]}, {member.offset}, {member.size}, "
                    f"{member.name}, {member.subtype}\n"
                )
    paths.append(fields_path)

    for snapshot in model.snapshots:
        path = out_dir / f"heaplens_output{snapshot.index}.txt"
        with path.open("w", encoding="utf-8", newline="\n") as out:
            out.write("# heaplens compact snapshot v2\n")
            out.write(f"# snapshot_index: {snapshot.index}\n")
            out.write(f"# time: {snapshot.time}\n")
            out.write(f"# page_size: {model.page_size}\n")
            out.write(f"# cache_line_size: {model.cache_line_size}\n")
            out.write(f"# adjacent_line_window: {model.adjacent_window}\n")
            out.write(f"# l1_sets: {model.l1_sets}\n")
            out.write(f"# pages_per_cluster: {pages_per_cluster}\n")
            out.write(
                "# object: offset, cache_line, l1_index, align_bucket, size, "
                "actual_size, split_offset, split_kind, is_container, type\n"
            )
            compact_pages = compact_snapshot_pages(snapshot, pages_per_cluster)
            for cluster in sorted(compact_pages):
                out.write(f"cluster {cluster}\n")
                for page_addr, objects in compact_pages[cluster]:
                    out.write(f"{page_addr}, {len(objects)}\n")
                    for obj in objects:
                        out.write(
                            f"{obj.offset}, {obj.cache_line}, {obj.l1_index}, "
                            f"{obj.align_bucket}, {obj.size}, {obj.actual_size}, "
                            f"{obj.split_offset}, {obj.split_kind}, "
                            f"{1 if obj.is_container else 0}, {obj.alias}\n"
                        )
        paths.append(path)
    return paths


def fmt_counter(counter: collections.Counter, limit: int = 8) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{key}:{value}" for key, value in counter.most_common(limit))


def summarize_objects(model: ExportModel, objects: list[Obj]) -> dict[str, object]:
    counts = collections.Counter(obj.alias for obj in objects)
    extra_crossings = collections.Counter(
        obj.alias for obj in objects if obj.extra_lines(model.cache_line_size) > 0
    )
    page_fragments = collections.Counter(obj.alias for obj in objects if obj.split_kind != "whole")
    containers = collections.Counter(obj.alias for obj in objects if obj.is_container)
    l1_start: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    l1_cover: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)

    for obj in objects:
        l1_start[obj.alias][obj.l1_index] += 1
        for line in obj.lines(model.cache_line_size):
            l1_set = ((obj.page_addr // model.cache_line_size) + line) % model.l1_sets
            l1_cover[obj.alias][l1_set] += 1

    line_map: dict[tuple[int, int], list[Obj]] = collections.defaultdict(list)
    window_map: dict[tuple[int, int], list[Obj]] = collections.defaultdict(list)
    for obj in objects:
        if obj.is_container:
            continue
        for line in obj.lines(model.cache_line_size):
            line_map[(obj.page_addr, line)].append(obj)
        for window in obj.windows(model.adjacent_window):
            window_map[(obj.page_addr, window)].append(obj)

    same_line_mixes = collections.Counter(
        tuple(sorted({obj.alias for obj in objs}))
        for objs in line_map.values()
        if len({obj.alias for obj in objs}) > 1
    )
    adjacent_mixes = collections.Counter(
        tuple(sorted({obj.alias for obj in objs}))
        for objs in window_map.values()
        if len({obj.alias for obj in objs}) > 1
    )

    field_crossings: collections.Counter[tuple[str, str]] = collections.Counter()
    for obj in objects:
        for field in field_entries_for_type(model.fields, obj.type_name):
            field_start = obj.actual_addr + field.offset
            field_end = field_start + field.size
            frag_start = obj.addr
            frag_end = obj.addr + obj.size
            if field_end <= frag_start or field_start >= frag_end:
                continue
            clipped_start = max(field_start, frag_start)
            clipped_end = min(field_end, frag_end)
            clipped_size = max(0, clipped_end - clipped_start)
            if clipped_size == 0:
                continue
            page_offset = clipped_start - obj.page_addr
            span = (page_offset + clipped_size - 1) // model.cache_line_size - page_offset // model.cache_line_size + 1
            ideal = max(1, math.ceil(clipped_size / model.cache_line_size))
            if span > ideal:
                field_crossings[(obj.alias, field.name)] += 1

    return {
        "counts": counts,
        "extra_crossings": extra_crossings,
        "page_fragments": page_fragments,
        "containers": containers,
        "same_line_mixes": same_line_mixes,
        "adjacent_mixes": adjacent_mixes,
        "l1_start": l1_start,
        "l1_cover": l1_cover,
        "field_crossings": field_crossings,
    }


def write_analysis(model: ExportModel, path: Path, pages_per_cluster: int) -> None:
    lines: list[str] = []
    lines.append("HEAPLENS ANALYSIS V2")
    lines.append(f"source_db: {model.db}")
    lines.append(f"generated_at: {model.generated_at}")
    lines.append(f"selected_pages: {model.selected_pages}")
    lines.append(f"clustered_pages: {model.clustered_pages}")
    lines.append(f"num_clusters: {model.num_clusters}")
    lines.append("")
    lines.append("ALIASES")
    for type_name in model.type_names:
        lines.append(f"  {model.aliases[type_name]}: {type_name}")
    field_aliases = [
        model.aliases[type_name]
        for type_name in model.type_names
        if field_entries_for_type(model.fields, type_name)
    ]
    lines.append(f"FIELDS_ALIASES: {', '.join(field_aliases) if field_aliases else 'none'}")
    lines.append("")

    aggregate: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for snapshot in model.snapshots:
        compact_pages = compact_snapshot_pages(snapshot, pages_per_cluster)
        objects = [
            obj
            for pages in compact_pages.values()
            for _page_addr, page_objects in pages
            for obj in page_objects
        ]
        summary = summarize_objects(model, objects)
        lines.append(
            f"SNAPSHOT {snapshot.index}: objects={len(objects)} "
            f"pages={len({obj.page_addr for obj in objects})} time={snapshot.time}"
        )
        for name in (
            "counts",
            "extra_crossings",
            "page_fragments",
            "containers",
            "same_line_mixes",
            "adjacent_mixes",
            "field_crossings",
        ):
            counter = summary[name]
            assert isinstance(counter, collections.Counter)
            lines.append(f"  {name}: {fmt_counter(counter, 12)}")
            aggregate[name].update(counter)

        l1_start = summary["l1_start"]
        l1_cover = summary["l1_cover"]
        assert isinstance(l1_start, dict)
        assert isinstance(l1_cover, dict)
        lines.append(
            "  l1_start_sets: "
            + "; ".join(
                f"{alias}:{len(counter)}sets top {fmt_counter(counter, 4)}"
                for alias, counter in sorted(l1_start.items())
            )
        )
        lines.append(
            "  l1_cover_sets: "
            + "; ".join(f"{alias}:{len(counter)}sets" for alias, counter in sorted(l1_cover.items()))
        )
        lines.append("")

    lines.append("AGGREGATE")
    for name in (
        "counts",
        "extra_crossings",
        "page_fragments",
        "containers",
        "same_line_mixes",
        "adjacent_mixes",
        "field_crossings",
    ):
        lines.append(f"  {name}: {fmt_counter(aggregate[name], 30)}")
    path.write_text("\n".join(lines) + "\n")


def export(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model = build_model(args)
    raw_path = args.output_dir / "heaplens_pages_v2.txt"
    compact_dir = args.output_dir / "compact"
    analysis_path = args.output_dir / "heaplens_analysis.txt"
    write_raw_v2(model, raw_path)
    compact_paths = write_compact_v2(model, compact_dir, args.pages_per_cluster)
    write_analysis(model, analysis_path, args.pages_per_cluster)

    print(f"Wrote raw: {raw_path}")
    print(f"Wrote compact files: {len(compact_paths)} in {compact_dir}")
    print(f"Wrote analysis: {analysis_path}")
    print(f"Types: {len(model.type_names)}")
    print(f"Selected pages: {model.selected_pages}")
    print(f"Clusters: {model.num_clusters}")
    print(f"Clustered pages: {model.clustered_pages}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export HeapLENS raw v2, compact v2, and analysis text from a SQLite DB."
    )
    parser.add_argument("db", type=Path, help="HeapLENS SQLite database")
    parser.add_argument("output_dir", type=Path, help="directory for generated v2 files")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--cache-line-size", type=int, default=DEFAULT_CACHE_LINE_SIZE)
    parser.add_argument("--adjacent-window", type=int, default=DEFAULT_ADJACENT_WINDOW)
    parser.add_argument("--l1-sets", type=int, default=DEFAULT_L1_SETS)
    parser.add_argument("--num-buckets", type=int, default=2000)
    parser.add_argument(
        "--cluster-alg",
        choices=["mbkmeans", "kmeans", "dbscan", "agglomerative", "meanshift"],
        default="mbkmeans",
    )
    parser.add_argument("--max-run-length", type=int, default=5)
    parser.add_argument("--max-runs-per-cluster", type=int, default=3)
    parser.add_argument("--pages-per-cluster", type=int, default=3)
    return parser.parse_args()


if __name__ == "__main__":
    export(parse_args())
