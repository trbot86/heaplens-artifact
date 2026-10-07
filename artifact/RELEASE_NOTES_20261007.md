# October 7 artifact fixes and validation

TPC-C tree allocations now have explicit typed records for both the ordinary
and separate-allocator paths. The separate allocator's frees are recorded too;
the logging calls do not change allocation ownership or the plain performance
build. Figure 6 now fails validation if its expected typed nodes are missing.

The baseline and optimized BCCO trace commands completed locally in 181.9 and
153.3 seconds, including builds and conversion. Both recorded about 644,000
56-byte tree-node allocations with type and source metadata. Independent
SQLite checks at 90% of each trace's timestamp interval found median node
payload densities of 2.81% and 76.56% in sampled node-containing 2 MiB regions.
The baseline GUI also displayed the named nodes and sparse regions. The
optimized GUI was not separately inspected. The two samples differ; these
observations are not new throughput results or an exact historical screenshot.

The trace defaults are two workers and two warehouses. The previous README's
24-worker description referred incorrectly to these diagnostic commands.
Performance experiments retain their own documented configurations.

The visualization backend now orders a converter-generated free before a
replacement allocation at the same timestamp. Previously, the replacement
could incorrectly appear immediately retired. Regression tests cover all input
orderings of typed and untyped replacements, later retirement, and unrelated
addresses. Independent replay checked the correction on three retained EFRB
traces. This does not resolve every historical cross-environment output mismatch.

## Remaining instrumentation work

A fresh archive extraction passed 41 focused regression tests, including native
exact allocation/free counts for both TPC-C allocators, logger-free plain
controls, timestamp ties, coverage rejection, logger lifecycle, HNSW query
logging and ASCYLIB retirement. The new coverage check also passed on both
complete BCCO trace databases. This is focused validation, not a full rerun of
every artifact experiment.

The shared automatic annotation driver still omits project-header edits unless
they are explicitly enabled. The TPC-C repair above supplies explicit records
at the record-manager boundary; it is not a general repair of that driver.
Broader header processing and interaction tests are pending. Custom allocation
paths require their own logging support. RocksDB header allocation coverage is
a priority for the follow-up audit; no missing-record claim is established here.

Plain benchmark throughput does not use this tracing pipeline. Historical
logging-overhead results describe their recorded builds and should not be read
as certified complete object coverage, especially for the affected TPC-C path.
Existing results are retained; this release does not substitute new overhead
measurements. A separate short-component-trace converter bucket overflow also
remains under investigation; the two full TPC-C traces passed conversion.
