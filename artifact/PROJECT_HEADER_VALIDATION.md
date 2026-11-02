# Automatic project-header annotation checks

The allocation annotation pass now includes headers within the copied project,
including headers above a selected build subdirectory. The checker compares
canonical filesystem paths, so relative includes and punctuation in directory
names do not change the boundary. System and external headers are excluded.
The default Clang diagnostic filter previously suppressed these header edits.

Both exporting `fixes.yaml` and applying edits immediately are exercised by
native tests. The immediate path passes a directory to `clang-apply-replacements`,
containing only the merged edits, and propagates failures. TPC-C's explicit node
hook uses `NOLINT(misc-allocation-logging)` to avoid a second automatic record.

The wrapper rejects conflicting edits at the same source location and stops
without applying a partial result if any translation unit fails. Identical
edits from repeated inclusion of a header are merged. Source-file identities
use canonical paths so different include spellings do not assign different
logging identifiers to the same file.

Placement-new annotations let the logger deduce the result type instead of
inserting a cast containing a template instantiation. For malloc-style calls,
the checker annotates the template definition and uses type names visible in
that scope; different instantiations cannot overwrite a shared header with
their concrete types.
Names outside templates retain their qualification. Custom factory methods
named `alloc` are not rewritten as allocator wrappers; allocations in their
bodies are still eligible. Qualified allocation calls use the function-name
token for insertion rather than an offset into the qualifier.

Run these checks inside the artifact image with the source at `/root/sifter`
and its pinned dependencies initialized:

```bash
cd /root/sifter/artifact/tests
HEAPLENS_RUN_INSTRUMENTATION_TESTS=1 \
  python3 -m unittest -v test_project_header_logging test_header_edge_cases test_header_merge test_tpcc_header_logging test_rocksdb_header_logging
```

The tests build the annotation tool and logger and execute small correctness
probes. Set `HEAPLENS_TEST_EVIDENCE` to a writable directory to retain transformed
sources, raw records, dictionaries and receipts there; otherwise they remain in
fresh temporary directories. These tests do not run the paper workloads.

| Probe | Checked result |
| --- | --- |
| Shared header, two translation units, template instantiations, `new` and `malloc` | Exactly 60 typed header allocations and 20 source-file allocations, each with one free, correct address, size and source |
| Immediate edits with spaces and punctuation in the output path | Same exact counts; external header remains unchanged |
| Native C header and source allocations | Exactly 40 typed 24-byte allocations and 40 frees |
| Placement-new template instances | Exactly 40 typed objects with independently checked 8-/24-byte sizes and backing addresses |
| Nested template malloc and assignment, two translation units | Exactly 42 typed allocations with independently checked 8-/16-/24-byte sizes |
| Factory named `alloc` and qualified `::malloc` | Factory call preserved; 40 exactly-once typed 24-byte allocations, including a namespace-qualified node type |
| Conflicting edits and a failed translation unit | Nonzero exit; no partial edits applied |
| TPC-C node allocator after automatic annotation | Ordinary and separate allocators each record exactly 1,000 typed 56-byte nodes and 1,000 frees |
| Pinned RocksDB SkipList and InlineSkipList headers | 31 nodes for each structure; inline nodes and 12 pointer-prefix regions match independently reported backing/key addresses; all 60 lookups succeed |

RocksDB uses its existing post-annotation repairs and explicit InlineSkipList
region hook. Its arena regions have different lifetime semantics from individual
heap allocations; the probe does not require an individual free for each region.
It uses a small reporting allocator and the pinned headers, not the complete
HashSkipList memtable or `db_bench` workload.

These checks do not establish complete allocation coverage, replay the full
figure commands, measure tracing overhead, or certify earlier measurements.
Enabling additional header annotations can change which events a future trace
records. The published October 7 archive contains the separately validated
explicit Figure 6 repair; this general tool change is subsequent work.
