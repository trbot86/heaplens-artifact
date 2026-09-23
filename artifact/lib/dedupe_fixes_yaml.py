#!/usr/bin/env python3
"""Deduplicate clang-tidy's fixes.yaml before clang-apply-replacements runs.

AllocationLoggingCheck.cpp assigns each source file a numeric "file ID"
(used inside the inserted `MemStamp(fileID, __LINE__)` call) by indexing
into a `std::map<std::string, int> filemap` that is per-clang-tidy-*process*
state (`filemap[FileName] = filemap.size()`). sifter.sh's `run-clang-tidy.py`
spawns one clang-tidy process per translation unit, so a header #included by
N different translation units can be assigned N different numeric file IDs
-- one per process, each computed independently from that TU's own include
order. For a small codebase (ASCYLIB, setbench) few enough TUs share few
enough headers that this never collides in practice. RocksDB is large
enough, with enough headers included by dozens of TUs (e.g.
table/block_based/block.h), that it reliably does: two TUs each propose a
*different* MemStamp(...) insertion at the exact same (file, byte offset),
and clang-apply-replacements-14 refuses to pick one -- it prints "The new
insertion has the same insert location as an existing replacement" for
every such pair and applies *nothing at all*, for the whole tree, not just
the conflicting files.

The fix: for each (file, offset) with more than one proposed replacement,
keep exactly one (the first seen) and drop the rest, then let
clang-apply-replacements-14 run against the deduplicated file. This means
a small number of call sites (the colliding ones) end up logged with a
file ID belonging to a different-but-real translation unit that also
allocates at that same source location -- i.e. the *type* and *fact of
allocation* logged there is still correct, only the "which file did this
allocation's stack frame belong to" attribution can be off for those
specific sites. Given HeapLENS's visualization is primarily type- and
layout-driven (not per-source-file), this is judged an acceptable,
documented trade-off rather than a reason to block the whole experiment.
A real fix belongs in AllocationLoggingCheck.cpp itself (e.g. a
content-hash-based file ID instead of a per-process insertion-order
counter, which would need to be shared/synchronized across processes to be
deterministic) -- out of scope for this artifact pass.

Usage: dedupe_fixes_yaml.py <fixes.yaml>
Rewrites the file in place; prints how many duplicate entries were dropped.
"""
import sys

import yaml


def normalize_path(path: str) -> str:
    return path[2:] if path.startswith("./") else path


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <fixes.yaml>", file=sys.stderr)
        return 1
    path = sys.argv[1]

    with open(path) as f:
        doc = yaml.safe_load(f)

    diagnostics = doc.get("Diagnostics") or []
    seen_locations = set()
    kept = []
    dropped = 0

    for diag in diagnostics:
        replacements = diag.get("DiagnosticMessage", {}).get("Replacements") or []
        if not replacements:
            # Diagnostic-only (e.g. inside a system header with no concrete
            # type to log): can't collide with anything, always keep.
            kept.append(diag)
            continue

        # AllocationLoggingCheck never emits more than one Replacement per
        # Diagnostics entry in practice; handle the general case anyway.
        key = tuple(
            (normalize_path(r["FilePath"]), r["Offset"], r["Length"])
            for r in replacements
        )
        if key in seen_locations:
            dropped += 1
            continue
        seen_locations.add(key)
        kept.append(diag)

    doc["Diagnostics"] = kept

    with open(path, "w") as f:
        yaml.safe_dump(doc, f, sort_keys=False)

    print(f"dedupe_fixes_yaml: kept {len(kept)}, dropped {dropped} duplicate insertion(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
