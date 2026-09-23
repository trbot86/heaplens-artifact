#!/usr/bin/env python3
"""Patch every class whose own `Allocate`/`AllocateAligned` method collides
with AllocationLoggingCheck's MATCH_FUNCTIONS list (which matches those
names bare, across the whole codebase -- see the file-header comment in
rocksdb_experiment.sh). The checker rewrites every call site
`obj->Allocate(args)` to `obj->Allocate<T, line, file>(args)`, so each such
class needs a templated overload with that exact shape, or the instrumented
tree won't compile. Two kinds of collision:

  1. Real allocators (memory/arena.h's Arena, memory/allocator.h's Allocator
     base interface, include/rocksdb/memory_allocator.h's MemoryAllocator,
     include/rocksdb/memtablerep.h's MemTableRep) -- these ARE memory
     allocation, but the template overload is a pure passthrough to the
     real (non-template) override, not a new logging call: whatever they
     return is immediately placement-new'd by the caller in every case this
     codebase actually hits, and HeapLENS's placement-new logging (always
     on; see sifter.sh's CPP_PLACEMENT_NEW) already captures the real
     allocated type at that point. Logging here too would double-log the
     same address, mislabeled as a generic byte buffer.
  2. Unrelated classes that just happen to also have a method named
     `Allocate` (tools/db_bench_tool.cc's TimestampEmulator -- allocates a
     *timestamp string*, not memory; include/rocksdb/env.h's WritableFile
     -- an fallocate()-style disk preallocation call; utilities/
     persistent_cache's CacheWriteBufferAllocator -- pops a pre-allocated
     buffer off a freelist, allocates nothing new). These need the exact
     same passthrough shape for the same "must compile" reason, even
     though logging would be actively wrong here (nothing is being
     allocated).

Usage: patch_allocate_overloads.py <instrumented_root>
Idempotent: skips any patch whose target text is already gone (so a
re-inserted overload from a previous run doesn't get inserted twice).
"""
import sys
from pathlib import Path

# Each entry: (relative path, exact text to find, text to insert immediately after it)
PATCHES = [
    (
        "memory/arena.h",
        "  char* Allocate(size_t bytes) override;\n",
        "\n"
        "  template <typename T, int line, uint16_t filename>\n"
        "  char* Allocate(size_t bytes) {\n"
        "    return Allocate(bytes);\n"
        "  }\n",
    ),
    (
        "memory/arena.h",
        "  char* AllocateAligned(size_t bytes, size_t huge_page_size = 0,\n"
        "                        Logger* logger = nullptr) override;\n",
        "\n"
        "  template <typename T, int line, uint16_t filename>\n"
        "  char* AllocateAligned(size_t bytes, size_t huge_page_size = 0,\n"
        "                        Logger* logger = nullptr) {\n"
        "    return AllocateAligned(bytes, huge_page_size, logger);\n"
        "  }\n",
    ),
    (
        "memory/allocator.h",
        "  virtual char* Allocate(size_t bytes) = 0;\n"
        "  virtual char* AllocateAligned(size_t bytes, size_t huge_page_size = 0,\n"
        "                                Logger* logger = nullptr) = 0;\n",
        "\n"
        "  template <typename T, int line, uint16_t filename>\n"
        "  char* Allocate(size_t bytes) {\n"
        "    return Allocate(bytes);\n"
        "  }\n"
        "\n"
        "  template <typename T, int line, uint16_t filename>\n"
        "  char* AllocateAligned(size_t bytes, size_t huge_page_size = 0,\n"
        "                        Logger* logger = nullptr) {\n"
        "    return AllocateAligned(bytes, huge_page_size, logger);\n"
        "  }\n",
    ),
    (
        "include/rocksdb/memory_allocator.h",
        "  virtual void* Allocate(size_t size) = 0;\n",
        "\n"
        "  template <typename T, int line, uint16_t filename>\n"
        "  void* Allocate(size_t size) {\n"
        "    return Allocate(size);\n"
        "  }\n",
    ),
    (
        "include/rocksdb/memtablerep.h",
        "  virtual KeyHandle Allocate(const size_t len, char** buf);\n",
        "\n"
        "  template <typename T, int line, uint16_t filename>\n"
        "  KeyHandle Allocate(const size_t len, char** buf) {\n"
        "    return Allocate(len, buf);\n"
        "  }\n",
    ),
    (
        "include/rocksdb/env.h",
        "  virtual Status Allocate(uint64_t /*offset*/, uint64_t /*len*/) {\n"
        "    return Status::OK();\n"
        "  }\n",
        "\n"
        "  template <typename T, int line, uint16_t filename>\n"
        "  Status Allocate(uint64_t offset, uint64_t len) {\n"
        "    return Allocate(offset, len);\n"
        "  }\n",
    ),
    (
        "tools/db_bench_tool.cc",
        "  Slice Allocate(char* scratch) {\n"
        "    // TODO: support larger timestamp sizes\n"
        "    assert(FLAGS_user_timestamp_size == 8);\n"
        "    assert(scratch);\n"
        "    uint64_t ts = timestamp_.fetch_add(1);\n"
        "    EncodeFixed64(scratch, ts);\n"
        "    return Slice(scratch, FLAGS_user_timestamp_size);\n"
        "  }\n",
        "\n"
        "  template <typename T, int line, uint16_t filename>\n"
        "  Slice Allocate(char* scratch) {\n"
        "    return Allocate(scratch);\n"
        "  }\n",
    ),
    (
        "utilities/persistent_cache/block_cache_tier_file_buffer.h",
        "  CacheWriteBuffer* Allocate() {\n"
        "    MutexLock _(&lock_);\n"
        "    if (bufs_.empty()) {\n"
        "      return nullptr;\n"
        "    }\n"
        "\n"
        "    assert(!bufs_.empty());\n"
        "    CacheWriteBuffer* const buf = bufs_.front();\n"
        "    bufs_.pop_front();\n"
        "    return buf;\n"
        "  }\n",
        "\n"
        "  template <typename T, int line, uint16_t filename>\n"
        "  CacheWriteBuffer* Allocate() {\n"
        "    return Allocate();\n"
        "  }\n",
    ),
]


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <instrumented_root>", file=sys.stderr)
        return 1
    root = Path(sys.argv[1])

    for rel_path, anchor, insertion in PATCHES:
        path = root / rel_path
        src = path.read_text()
        if insertion in src:
            print(f"patch_allocate_overloads: {rel_path}: already patched, skipping")
            continue
        count = src.count(anchor)
        if count != 1:
            print(
                f"patch_allocate_overloads: ERROR: {rel_path}: anchor text found "
                f"{count} time(s) (expected 1) -- RocksDB source at this pinned "
                f"commit may not match what this script expects",
                file=sys.stderr,
            )
            return 1
        path.write_text(src.replace(anchor, anchor + insertion, 1))
        print(f"patch_allocate_overloads: {rel_path}: patched")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
