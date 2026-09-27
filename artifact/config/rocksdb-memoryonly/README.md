# Memory-only RocksDB options

The performance driver uses `skip_list.ini` for InlineSkipList. The
`prefix_hash.ini` file retains the separate memory-only HashSkipList
configuration for reference; the default HashSkipList experiment instead
uses a 256-MiB write buffer with flushing and compaction enabled, as described
in the [reproduction configurations](../../REPRODUCTION_CONFIGURATIONS.md#rocksdb-hashskiplist-field-reordering).

These complete options files preserve the effective settings used in the
memory-only verification on the dual Xeon Gold 5220R machine, including the
1-MiB arena block size and HashSkipList's 1,048,576 hash buckets. Loading only
a bare hash-factory name would instead select the library's 1,000,000-bucket
default. The memory-only options helper changes only the prefix/plain-table key lengths and
background-job limit to match the requested key size and thread count, and
saves the resulting file beside the run's protocol.

The source is RocksDB revision `19e4aba3db75bd6add7177164c892ab6cdfd50b3`
with the artifact's existing `rocksdb-historical.patch`. Relative to its
retained disk-backed effective options, three values were changed:

- `write_buffer_size=49928994816` (46.5 GiB).
- `disable_auto_compactions=true`.
- `avoid_flush_during_shutdown=true`.

The benchmark command separately disables WAL and synchronous writes and
uses `filluniquerandom,readwhilewriting`, without a compaction wait.
The serialized private `ErrorHandlerListener` entry is omitted: unchanged
db_bench installs that listener after loading options. No benchmark source
modification is needed to suppress shutdown flushing.

The runner checks each trial's effective OPTIONS against the requested settings
and checks the complete DB lifetime for data persistence. It keeps logs and
metadata for inspection; it never removes generated tables to make a run
pass validation.
