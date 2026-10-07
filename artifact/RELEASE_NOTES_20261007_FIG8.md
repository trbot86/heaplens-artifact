# Figure 8 update: version 2026.10.07.1

The visualization backend now associates the HashSkipList bucket's recorded
fields with its allocation type despite the equivalent `const char*` versus
`char const*` spellings used by compiler metadata and runtime names. The repair
is an exact alias for the pinned bucket type and uses existing database field
offsets. It does not change application layouts, logging or measured throughput.

Figure 8 instructions now name the precise bucket type, explain field
visibility controls and byte-detail zoom, and put `HEAPLENS_CACHE_BUDGET_MB`
next to the GUI command. The memory-budget error also explains that option
and the additional server/browser memory required.

Nine focused regressions pass. Native checks confirm the 56-byte baseline
bucket, its four-byte gaps at offsets 36 and 52, and the reordered 48-byte
bucket without those gaps. On a retained baseline database, all 1,100 existing
cache columns remain identical and nine field columns become available; the
database is unchanged. An actual baseline GUI check shows both padding gaps.
The optimized layout has native validation, but its browser view has not been
checked in this update. These checks are not new performance measurements or
validation of the evaluator's own databases.

The [tool TODO](TOOL_TODO.md) records the agreed general solution: make allocation
and compiler field metadata use consistent type names while preserving type
distinctions and supporting existing traces. That broader solution is not yet
implemented. The separate general header-annotation candidate remains excluded
pending repair and validation of its nested placement-new logging interaction.

The earlier [Figure 6 release notes](RELEASE_NOTES_20261007.md) remain available.
Historical results and the preceding Zenodo version are preserved.
