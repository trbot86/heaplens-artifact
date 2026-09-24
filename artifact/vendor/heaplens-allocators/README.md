# Retained TPC-C segregation allocator

`libjemalloc-heaplens.so` is the Linux x86-64 jemalloc 5.3.0 library retained
from the authors' HeapLENS experiment tree (`sifter/jemalloc/lib/libjemalloc.so`).
SHA-256: `c516606efbdb708f503bc0f249061e492df04010a7292056281a0e9df6cbb3da`.
Its license is in `COPYING`.

The TPC-C drivers copy this file into each experiment's `src/lib/` directory.
`MEMHOOK_SEG_DS` routes record-managed tree objects through this library;
ordinary allocations use the process-wide allocator selected by the experiment
(SetBench's jemalloc 5.0.1 or mimalloc 1.6.3). Both sides of a reclamation or
row-padding comparison retain the same allocator configuration.

The separate library must not resolve to the process-wide allocator. Reopening
the already loaded global library with `dlopen` does not create a new instance.
Repeated opens of this separate library likewise share one instance; they do
not create private allocators per table or per object type.
