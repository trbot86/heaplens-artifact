# Allocation annotation correctness

The general project-header candidate records a standard global C++ allocation
before its constructors execute. The compiler supplies the requested extent to
the `MemhookNew<T>` allocation overload, including array storage. This avoids
using a single pending allocation record across nested constructors. Matching
delete overloads preserve cleanup when construction throws.
For ordinary `new[]`, this is the allocator's complete extent, including an
ABI array cookie when present. The recorded allocation base need not be the
first element's address; these checks do not certify field overlays for such
array cookies.

Placement new retains its original allocation function and records the
returned object independently through `MemPlacementStamp`. Placement arrays
capture their bound once at its original evaluation position, preserve its
signedness, and record the complete constructed object range after successful
construction. They retain standard placement-new array cookie behavior. An
unsuccessful placement construction does not create a typed object event.
This path does not consume
an enclosing pending allocation. Recording a carved object and its backing
allocation does not make their byte counts disjoint.

The annotator uses type spelling from the source header, so different template
instantiations do not insert conflicting concrete types into the same source
location. Standard ordinary, array, nothrow and C++17 aligned allocating forms
have native tests. Existing transformed sources using the legacy `MemStamp`
expression must be regenerated to use this path; the legacy interface is not
the correctness authority for nested construction.

Unsupported custom allocation/deallocation functions, deduced `new auto`, and
implicit or class-valued placement-array bounds are rejected with diagnostics
instead of receiving guessed extents or repeating a user-defined conversion.
In particular, substituting a custom placement allocation function for standard
`new(storage) T[n]` can introduce an array cookie and change the storage ABI.
Custom allocation functions need explicit allocation/region hooks. This is not a claim of
complete C++ allocation interception.

RocksDB's pinned `StatisticsData` allocator now supplies explicit tag-taking
new/delete overloads. They delegate to its original cache-line-aligned
allocator, record the compiler-supplied extent before construction, and retain
its cleanup when construction throws. The original allocation functions carry
the `heaplens_tagged_allocation` Clang annotation to opt into this protocol.
Unmarked custom allocators still fail with a diagnostic. The adapter is applied
before source analysis, including for the generic `CoreLocalArray<T>` caller.

The final synchronous trace flush retries interrupted and short writes. A write
error or zero-progress write exits with status 94 and marks the trace invalid,
instead of allowing an incomplete trace to appear successful. This does not
promise storage durability after a power failure; it verifies completed writes.
Failure to open the binary output or open/write/close its type dictionary also
marks the trace invalid and exits with status 94. A complete binary stream is
insufficient if its type dictionary cannot be published.

Retirement events are copied before calling the underlying free/retirement
function. An allocator can make an address available to another thread before
its free call returns; recording afterward can invert the two lifetimes. A
deterministic two-thread native test forces that interleaving for ordinary
free, scalar delete and array delete, and checks allocation/free/allocation/free
order. Null free/delete calls emit no event. These timestamps describe the
instrumented API boundary, not the allocator's internal reclamation instant.

Run the native checks inside the artifact image:

```bash
cd artifact/tests
HEAPLENS_RUN_INSTRUMENTATION_TESTS=1 python3 -m unittest -v \
  test_new_expression_logging test_header_edge_cases \
  test_project_header_logging test_tpcc_header_logging \
  test_rocksdb_header_logging test_custom_allocator_logging \
  test_logger_lifecycle test_logger_tail test_retirement_order
```

The checks compare addresses, extents, type names, event multiplicity and
retirements against the native program's observations. They cover nested
allocating and placement constructors, zero/nonzero child offsets, arrays,
constructor exceptions, nothrow failure, alignment and multiple producer
threads. Correct compilation and presence of a type name alone do not establish
correct tracing. Full application validation is tracked separately in the
author evidence; a passing focused suite does not certify every application.
