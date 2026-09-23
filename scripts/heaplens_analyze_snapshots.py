#!/usr/bin/env python3
"""Summarize compact HeapLENS page-layout snapshot exports.

The expected input directory contains:
  - heaplens_output*.txt
  - heaplens_types.txt
  - heaplens_fields.txt, optionally
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import math
import re
from pathlib import Path

CACHE_LINE = 64
ADJACENT_LINE_WINDOW = 128
PAGE_SIZE = 4096
L1_SETS = 64


@dataclasses.dataclass(frozen=True)
class Obj:
    page: int
    cluster: int
    offset: int
    cache_line: int
    l1_index: int
    align_bucket: str
    size: int
    alias: str
    actual_size: int
    split_offset: int
    split_kind: str
    is_container: bool

    def first_line(self, cache_line: int) -> int:
        return self.offset // cache_line

    def last_line(self, cache_line: int) -> int:
        return (self.offset + self.size - 1) // cache_line if self.size else self.first_line(cache_line)

    def line_span(self, cache_line: int) -> int:
        return self.last_line(cache_line) - self.first_line(cache_line) + 1

    def ideal_lines(self, cache_line: int) -> int:
        return max(1, math.ceil(self.size / cache_line))

    def extra_lines(self, cache_line: int) -> int:
        return self.line_span(cache_line) - self.ideal_lines(cache_line)

    def lines(self, cache_line: int) -> range:
        return range(self.first_line(cache_line), self.last_line(cache_line) + 1)

    def windows(self, window_size: int) -> range:
        first = self.offset // window_size
        last = (self.offset + max(self.size, 1) - 1) // window_size
        return range(first, last + 1)


def parse_types(path: Path) -> dict[str, str]:
    types: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        alias, type_name = [part.strip() for part in line.split(",", 1)]
        types[alias] = type_name
    return types


def parse_fields(path: Path) -> dict[str, list[tuple[int, int, str, str]]]:
    fields: dict[str, list[tuple[int, int, str, str]]] = collections.defaultdict(list)
    if not path.exists():
        return {}

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split(",", 4)]
        if len(parts) != 5:
            continue
        alias, offset, size, name, subtype = parts
        fields[alias].append((int(offset), int(size), name, subtype))

    return dict(fields)


def parse_snapshot(path: Path) -> tuple[dict[str, str], list[Obj]]:
    meta: dict[str, str] = {}
    objects: list[Obj] = []
    cluster: int | None = None
    page: int | None = None

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue

        if line.startswith("#"):
            match = re.match(r"#\s*([^:]+):\s*(.*)", line)
            if match:
                meta[match.group(1).strip()] = match.group(2).strip()
            continue

        if line.startswith("cluster "):
            cluster = int(line.split()[1])
            page = None
            continue

        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 2:
            page = int(parts[0])
            continue

        if len(parts) in (6, 10):
            if cluster is None or page is None:
                raise ValueError(f"object before page/cluster in {path}: {line}")
            if len(parts) == 6:
                offset, cache_line, l1_index, align_bucket, size, alias = parts
                actual_size = size
                split_offset = "0"
                split_kind = "legacy_fragment" if int(offset) + int(size) > PAGE_SIZE or (int(offset) == 0 and int(size) != PAGE_SIZE) else "whole"
                is_container = "0"
            else:
                (
                    offset,
                    cache_line,
                    l1_index,
                    align_bucket,
                    size,
                    actual_size,
                    split_offset,
                    split_kind,
                    is_container,
                    alias,
                ) = parts
            objects.append(
                Obj(
                    page=page,
                    cluster=cluster,
                    offset=int(offset),
                    cache_line=int(cache_line),
                    l1_index=int(l1_index),
                    align_bucket=align_bucket,
                    size=int(size),
                    alias=alias,
                    actual_size=int(actual_size),
                    split_offset=int(split_offset),
                    split_kind=split_kind,
                    is_container=is_container in ("1", "true", "True"),
                )
            )
            continue

        raise ValueError(f"unrecognized line in {path}: {line}")

    return meta, objects


def summarize_snapshot(
    path: Path,
    types: dict[str, str],
    fields: dict[str, list[tuple[int, int, str, str]]],
) -> dict[str, object]:
    meta, objects = parse_snapshot(path)
    cache_line = int(meta.get("cache_line_size", CACHE_LINE))
    adjacent_window = int(meta.get("adjacent_line_window", ADJACENT_LINE_WINDOW))
    l1_sets = int(meta.get("l1_sets", L1_SETS))
    counts = collections.Counter(obj.alias for obj in objects)
    sizes: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    align: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    extra_crossings: collections.Counter[str] = collections.Counter()
    page_fragments: collections.Counter[str] = collections.Counter()
    l1_start: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    l1_cover: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)

    for obj in objects:
        sizes[obj.alias][obj.size] += 1
        align[obj.alias][obj.align_bucket] += 1
        l1_start[obj.alias][obj.l1_index] += 1
        for line in obj.lines(cache_line):
            l1_cover[obj.alias][((obj.page // cache_line) + line) % l1_sets] += 1
        if obj.extra_lines(cache_line) > 0:
            extra_crossings[obj.alias] += 1
        if obj.split_kind != "whole":
            page_fragments[obj.alias] += 1

    line_map: dict[tuple[int, int], list[Obj]] = collections.defaultdict(list)
    window_map: dict[tuple[int, int], list[Obj]] = collections.defaultdict(list)
    for obj in objects:
        if obj.is_container:
            continue
        for line in obj.lines(cache_line):
            line_map[(obj.page, line)].append(obj)
        for window in obj.windows(adjacent_window):
            window_map[(obj.page, window)].append(obj)

    same_line_mixes = collections.Counter(
        tuple(sorted({obj.alias for obj in objs}))
        for objs in line_map.values()
        if len({obj.alias for obj in objs}) > 1
    )
    adjacent_128_mixes = collections.Counter(
        tuple(sorted({obj.alias for obj in objs}))
        for objs in window_map.values()
        if len({obj.alias for obj in objs}) > 1
    )

    field_extra_crossings: collections.Counter[tuple[str, str]] = collections.Counter()
    for obj in objects:
        for field_offset, field_size, name, _subtype in fields.get(obj.alias, []):
            field_start = field_offset
            field_end = field_start + field_size
            frag_start = obj.split_offset
            frag_end = obj.split_offset + obj.size
            if field_end <= frag_start or field_start >= frag_end:
                continue

            clipped_start = max(field_start, frag_start)
            clipped_end = min(field_end, frag_end)
            clipped_size = clipped_end - clipped_start
            abs_offset = obj.offset + (clipped_start - frag_start)
            span = (abs_offset + clipped_size - 1) // cache_line - abs_offset // cache_line + 1
            ideal = max(1, math.ceil(clipped_size / cache_line))
            if span > ideal:
                field_extra_crossings[(obj.alias, name)] += 1

    return {
        "meta": meta,
        "objects": len(objects),
        "pages": len({obj.page for obj in objects}),
        "counts": counts,
        "sizes": sizes,
        "align": align,
        "extra_crossings": extra_crossings,
        "page_fragments": page_fragments,
        "containers": collections.Counter(obj.alias for obj in objects if obj.is_container),
        "same_line_mixes": same_line_mixes,
        "adjacent_128_mixes": adjacent_128_mixes,
        "l1_start": l1_start,
        "l1_cover": l1_cover,
        "field_extra_crossings": field_extra_crossings,
    }


def fmt_counter(counter: collections.Counter, limit: int = 8) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{key}:{value}" for key, value in counter.most_common(limit))


def snapshot_sort_key(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    if not match:
        return -1
    return int(match.group(1))


def prefer_with_fields(folder: Path, no_auto_with_fields: bool) -> Path:
    if no_auto_with_fields or folder.name.endswith("_with_fields"):
        return folder

    sibling = folder.with_name(f"{folder.name}_with_fields")
    if sibling.is_dir():
        return sibling
    return folder


def print_summary(folder: Path, no_auto_with_fields: bool) -> None:
    analysis_folder = prefer_with_fields(folder, no_auto_with_fields)
    types = parse_types(analysis_folder / "heaplens_types.txt")
    fields = parse_fields(analysis_folder / "heaplens_fields.txt")

    if analysis_folder != folder:
        print(f"USING_WITH_FIELDS: {analysis_folder}")
        print(f"REQUESTED_FOLDER: {folder}")
        print()
    print("ALIASES")
    for alias, type_name in sorted(types.items()):
        print(f"  {alias}: {type_name}")
    print(f"FIELDS_ALIASES: {', '.join(sorted(fields)) if fields else 'none'}")
    print()

    aggregate: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for path in sorted(analysis_folder.glob("heaplens_output*.txt"), key=snapshot_sort_key):
        summary = summarize_snapshot(path, types, fields)
        meta = summary["meta"]
        assert isinstance(meta, dict)
        print(
            f"SNAPSHOT {meta.get('snapshot_index', path.stem)}: "
            f"objects={summary['objects']} pages={summary['pages']} time={meta.get('time')}"
        )
        for name in ("counts", "extra_crossings", "page_fragments", "containers", "same_line_mixes", "adjacent_128_mixes"):
            counter = summary[name]
            assert isinstance(counter, collections.Counter)
            print(f"  {name}: {fmt_counter(counter, 12)}")
            aggregate[name].update(counter)

        l1_start = summary["l1_start"]
        l1_cover = summary["l1_cover"]
        assert isinstance(l1_start, dict)
        assert isinstance(l1_cover, dict)
        print(
            "  l1_start_sets: "
            + "; ".join(
                f"{alias}:{len(counter)}sets top {fmt_counter(counter, 4)}"
                for alias, counter in sorted(l1_start.items())
            )
        )
        print(
            "  l1_cover_sets: "
            + "; ".join(f"{alias}:{len(counter)}sets" for alias, counter in sorted(l1_cover.items()))
        )

        field_crossings = summary["field_extra_crossings"]
        assert isinstance(field_crossings, collections.Counter)
        print(f"  field_extra_crossings: {fmt_counter(field_crossings, 12)}")
        aggregate["field_extra_crossings"].update(field_crossings)
        print()

    print("AGGREGATE")
    for name in (
        "counts",
        "extra_crossings",
        "page_fragments",
        "containers",
        "same_line_mixes",
        "adjacent_128_mixes",
        "field_extra_crossings",
    ):
        print(f"  {name}: {fmt_counter(aggregate[name], 30)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Directory containing heaplens_output*.txt and lookup files.")
    parser.add_argument(
        "--no-auto-with-fields",
        action="store_true",
        help="Analyze the exact folder passed instead of preferring a sibling *_with_fields export.",
    )
    args = parser.parse_args()
    print_summary(args.folder, args.no_auto_with_fields)


if __name__ == "__main__":
    main()
