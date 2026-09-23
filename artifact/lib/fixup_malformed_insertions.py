#!/usr/bin/env python3
"""Fix a handful of AllocationLoggingCheck insertions that are outright
malformed or wrong at RocksDB's scale/complexity, beyond the general
"(anonymous namespace)" case handled by fixup_anon_namespace_casts.py.
Each of these was found by iterating build errors while bringing up the
rocksdb_hsl experiment; see the comment above each fix for the specific
mechanism. All are narrow, deterministic text substitutions scoped to one
file each -- not general algorithms -- because each is a different failure
shape of the same underlying issue (the checker prints a type name that
isn't valid, or isn't correct, at the point it's inserted).

Usage: fixup_malformed_insertions.py <instrumented_root>
Idempotent (each fix's target text won't match a second time once applied).
"""
import re
import sys
from pathlib import Path


def fix_autovector(root: Path) -> None:
    # util/autovector.h: placement-new inside autovector<T,N>'s own member
    # functions gets cast to a qualified "rocksdb::autovector::value_type"
    # or "rocksdb::autovector<SomeConcreteType, N>::value_type" -- either
    # the injected-class-name printed without its own template arguments
    # (not valid as a qualifier here), or some OTHER instantiation's
    # concrete type entirely (valid syntax, but the wrong type whenever
    # this method is instantiated for a different T/N -- the same root
    # cause as table/iterator.cc's TValue bug below, just for a class
    # instead of a function template). Which exact form shows up isn't
    # deterministic between runs (depends on which instantiation the
    # checker happens to analyze), so match both generally. "value_type" is
    # autovector's own nested typedef, already visible unqualified from
    # within its member functions, so just drop whatever qualifier prefix
    # was printed.
    path = root / "util/autovector.h"
    src = path.read_text()
    pattern = re.compile(
        r"rocksdb::autovector(?:<[^()>]*>)?::value_type", re.DOTALL
    )
    new_src, n = pattern.subn("value_type", src)
    if n:
        path.write_text(new_src)
    print(f"fixup_malformed_insertions: autovector.h: fixed {n}")


def fix_iterator_cc(root: Path) -> None:
    # table/iterator.cc: NewErrorInternalIterator<TValue>/
    # NewEmptyInternalIterator<TValue> are template functions; the checker
    # analyzes whichever instantiation it happens to encounter first
    # (varies run to run -- observed TValue=IndexValue and TValue=Slice)
    # and bakes that one concrete type into the cast instead of the
    # function's own template parameter TValue, so it's simply the wrong
    # type for every OTHER instantiation. The line directly below each
    # cast already constructs `EmptyInternalIterator<TValue>(...)` --
    # restore that same, correct, generic type in the cast.
    path = root / "table/iterator.cc"
    src = path.read_text()
    # Anchored to the cast's own parens (MemStamp(...) * (TYPE*) new (...)),
    # AND bounded to within one statement ([^;{}]*?, not .*?) so this can
    # only ever match that one cast expression. Without the statement
    # bound, a non-greedy .*? has no reason to stop at the nearby (and
    # unrelated) `sizeof(EmptyInternalIterator<TValue>)` -- which has no
    # "*)" right after ">", so the engine just keeps extending the match
    # across the rest of that statement, the next one, etc., until it
    # finds ANY later ">*)" -- silently swallowing real code in between.
    pattern = re.compile(r"\(EmptyInternalIterator<[^;{}]*?>\*\)", re.DOTALL)
    new_src, n = pattern.subn("(EmptyInternalIterator<TValue>*)", src)
    if n:
        path.write_text(new_src)
    print(f"fixup_malformed_insertions: iterator.cc: fixed {n}")


def fix_skiplist_h(root: Path) -> None:
    # memtable/skiplist.h: same root cause as autovector.h above, but for
    # SkipList<Key, Comparator>'s own Node type -- the checker prints
    # whichever concrete instantiation it happened to analyze (which
    # instantiation varies run to run depending on build/analysis order;
    # observed both HashSkipListRep's own bucket SkipList<const char*,
    # const MemTableRep::KeyComparator&> -- the exact data structure this
    # experiment is about -- and WriteBatchWithIndex's SkipList<
    # WriteBatchIndexEntry*, const WriteBatchEntryComparator&>) instead of
    # the enclosing template's own type parameters. "Node" is already
    # visible unqualified from within SkipList<Key,Comparator>'s own member
    # functions, regardless of what Key/Comparator actually are.
    path = root / "memtable/skiplist.h"
    src = path.read_text()
    # The template-argument part is OPTIONAL: sometimes the checker prints
    # the bare injected-class-name with no arguments at all
    # ("rocksdb::SkipList::Node", itself not valid outside the template's
    # own scope), other times a fully concrete instantiation
    # ("rocksdb::SkipList<const char*, ...>::Node", valid syntax but the
    # wrong type). [^;{}]* (not .*?) bounds the argument-list match to
    # within a single statement, so a missing "::Node" after some OTHER,
    # unrelated SkipList<...> usage can't make this run away matching all
    # the way to a distant, unrelated "::Node" occurrence later in the file.
    pattern = re.compile(
        r"(?:struct |class )?rocksdb::SkipList(?:<[^;{}]*?>)?::Node", re.DOTALL
    )
    new_src, n = pattern.subn("Node", src)
    if n:
        path.write_text(new_src)
    print(f"fixup_malformed_insertions: skiplist.h: fixed {n}")


def fix_toku_static_alloc_calls(root: Path) -> None:
    # utilities/transactions/lock/range/range_tree/lib/locktree/{treenode,
    # wfg}.cc: TokuDB's vendored lock-tree library has a couple of static
    # factory methods literally named `alloc` (ClassName::alloc(...)). For
    # these specific call sites the checker computed the wrong insertion
    # offset and spliced its `<T, line, file>` text into the MIDDLE of the
    # class name token itself (e.g. "treenode::alloc(...)" became
    # "treen<class toku::treenode, 230, 269>ode::alloc(...)") rather than
    # after it -- not just a wrong type, a corrupted identifier, so there's
    # nothing to recover; just restore the original, un-instrumented call.
    # These are internal TokuDB lock-tree node allocations, unrelated to
    # this experiment's HashSkipList memtable subject.
    fixes = [
        (
            "utilities/transactions/lock/range/range_tree/lib/locktree/treenode.cc",
            re.compile(r"treen<class toku::treenode, \d+, \d+>ode::alloc"),
            "treenode::alloc",
        ),
        (
            "utilities/transactions/lock/range/range_tree/lib/locktree/wfg.cc",
            re.compile(r"node:<struct toku::wfg::node, \d+, \d+>:alloc"),
            "node::alloc",
        ),
    ]
    for rel_path, pattern, replacement in fixes:
        path = root / rel_path
        src = path.read_text()
        new_src, n = pattern.subn(replacement, src)
        if n:
            path.write_text(new_src)
        print(f"fixup_malformed_insertions: {rel_path}: fixed {n}")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <instrumented_root>", file=sys.stderr)
        return 1
    root = Path(sys.argv[1])

    fix_autovector(root)
    fix_iterator_cc(root)
    fix_skiplist_h(root)
    fix_toku_static_alloc_calls(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
