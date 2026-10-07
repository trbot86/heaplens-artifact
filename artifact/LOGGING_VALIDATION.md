# Allocation annotation correctness

The general project-header candidate records a standard global C++ allocation
before its constructors execute. The compiler supplies the requested extent to
the `MemhookNew<T>` allocation overload, including array storage. This avoids
using a single pending allocation record across nested constructors. Matching
delete overloads preserve cleanup when construction throws.

Scalar placement new retains its original allocation function and records the
returned object independently through `MemPlacementStamp`. It does not consume
an enclosing pending allocation. Recording a carved object and its backing
allocation does not make their byte counts disjoint.

The annotator uses type spelling from the source header, so different template
instantiations do not insert conflicting concrete types into the same source
location. Standard ordinary, array, nothrow and C++17 aligned allocating forms
have native tests. Existing transformed sources using the legacy `MemStamp`
expression must be regenerated to use this path; the legacy interface is not
the correctness authority for nested construction.

Unsupported custom allocation functions, deduced `new auto`, and placement-new
arrays are rejected with diagnostics instead of receiving guessed extents.
In particular, substituting a custom placement allocation function for standard
`new(storage) T[n]` can introduce an array cookie and change the storage ABI.
Such cases need explicit allocation/region hooks. This is not a claim of
complete C++ allocation interception.

Run the native checks inside the artifact image:

```bash
cd artifact/tests
HEAPLENS_RUN_INSTRUMENTATION_TESTS=1 python3 -m unittest -v \
  test_new_expression_logging test_header_edge_cases \
  test_project_header_logging test_tpcc_header_logging \
  test_rocksdb_header_logging test_logger_lifecycle
```

The checks compare addresses, extents, type names, event multiplicity and
retirements against the native program's observations. They cover nested
allocating and placement constructors, zero/nonzero child offsets, arrays,
constructor exceptions, nothrow failure, alignment and multiple producer
threads. Correct compilation and presence of a type name alone do not establish
correct tracing. Full application validation is tracked separately in the
author evidence; a passing focused suite does not certify every application.
