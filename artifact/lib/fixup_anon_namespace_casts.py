#!/usr/bin/env python3
"""Fix AllocationLoggingCheck's malformed casts for types declared inside an
anonymous namespace.

When the checker prints the static type of a placement-new target that
lives in an anonymous namespace (e.g. `namespace { class LevelIterator {
... }; }` in db/version_set.cc), it prints the type's fully qualified name
literally, including the human-readable "(anonymous namespace)" label clang
itself uses in diagnostics -- e.g. `(class rocksdb::(anonymous
namespace)::LevelIterator*)`. That's not valid C++ syntax (you cannot name
an anonymous namespace in code), so every instrumented placement-new of
such a type fails to compile.

The fix works because every such site is, by construction, used from
within a scope that can already see the type unqualified (either directly
inside the same anonymous namespace, or inside one of that type's own
member functions) -- anonymous-namespace members don't need qualification
to be visible there. So it's always correct to just drop the
`rocksdb::(anonymous namespace)::` (and any leading `class `/`struct
`/`union ` keyword clang printed before it) prefix and keep the rest of the
qualified name as-is.

Usage: fixup_anon_namespace_casts.py <root_dir>
Scans <root_dir> for *.cc/*.h files containing "(anonymous namespace)::" and
rewrites them in place; prints how many occurrences were fixed per file.
"""
import re
import sys
from pathlib import Path

# Matches an optional leading class-key keyword, then the literal
# "<ns>::(anonymous namespace)::" prefix clang prints. Keeps whatever
# qualified name follows (e.g. "MemTableInserter::HintMap").
PATTERN = re.compile(r"\b(?:class |struct |union )?[A-Za-z_][A-Za-z0-9_]*::\(anonymous namespace\)::")


def fix_file(path: Path) -> int:
    text = path.read_text()
    new_text, count = PATTERN.subn("", text)
    if count:
        path.write_text(new_text)
    return count


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <root_dir>", file=sys.stderr)
        return 1
    root = Path(sys.argv[1])

    total = 0
    for pattern in ("*.cc", "*.h", "*.cpp", "*.hpp"):
        for path in root.rglob(pattern):
            count = fix_file(path)
            if count:
                print(f"fixup_anon_namespace_casts: {path}: fixed {count}")
                total += count

    print(f"fixup_anon_namespace_casts: fixed {total} occurrence(s) total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
