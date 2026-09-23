## Paper data

The `paper_data.xlsx` file contains the data presented in Table 1 of the paper.
Raw data tables are collocated with pivot tables giving the average of a
variable (e.g. throughput, cache misses etc.) for different experiment types
and thread counts. Where present, the third column of each pivot table gives
the percentage increase/decrease of the corresponding variable.

The file consists of the following six sheets:

1. pyke ASCYLIB: contains all of the ASCYLIB experiments. The `exp-1M` data
at the top of the sheet were used for the DVY/HJ trees, and the `exp-200k`
data at the bottom of the sheet were used for the EFRB tree.

2. pyke TPCC ellen mimalloc: contains the TPC-C experiments using the EFRB
tree.

3. pyke TPCC bronson: contains the TPC-C experiments using the BCCO tree.

4. malphite RocksDB ISL: contains the RocksDB experiments using the
Inline SkipList memtable.

5. pyke RocksDB HSL: contains the RocksDB experiments using the Hash
SkipList memtable.

6. pyke HeapLENS overhead: contains the overhead experiments from Appendix C.
