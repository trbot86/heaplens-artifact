# Event-name lookups, original extents, and continuation markers

September 29, 2026. Local changes on `codex/camera-ready-sampling`; evaluator-facing
`main` and retained application traces/databases are unchanged.

## Implementation

The converter writes integer `FILE_ID` and `TYPE_ID` values into `EVENTS`.
`FILE_NAMES` and `TYPE_NAMES` contain each ID's string once, keyed by SQLite
`INTEGER PRIMARY KEY`. A read-compatible `SUPERTABLE` view resolves both names
with joins. Existing queries therefore keep the same names and field ordering;
`ACTUALSIZE` is appended. The view is read-only; code that writes directly to
the old `SUPERTABLE` table would need updating.

`ACTUALSIZE` is the original event/object size, captured before page splitting
and retained for both allocation and free fragments, including pages added to
satisfy per-type minimums. The raw logger format and application instrumentation
are unchanged. The converter's per-fragment bookkeeping gains one `size_t`;
the backend/GUI also carry the extra numeric field. No per-object extent join
or reconstruction from neighbouring sampled pages is necessary.

The GUI compares the original `[actualAddr, actualAddr + actualSize)` extent
with the page boundaries. Zigzags indicate continuation on either side; exact
boundary endings are not marked. Markers follow object lifetime and type
visibility. Huge-page overview markers aggregate live visible objects; zooming
clips markers at page boundaries outside the visible region. Candidate
boundary-crossing events are memoized, avoiding a complete extra history scan
on each timeline movement. Markers do not intercept pointer events.

Old databases still load. Their unknown original sizes use a zero sentinel and
suppress both markers. Regenerating a database from its retained raw trace
provides extents; no new application run is required.

## Join-cost comparison

Inputs: retained Valkey (1,024,766 event-fragment records) and TPC-C/BCCO
(981,159 records) databases. Local Docker, two-CPU quota, 8-GiB memory limit,
`heaplens-reviewer-smoke:20260929`. One discarded warmup and five alternating
trials per schema/stage, fresh Python process each trial. OS caches were not
flushed. Each dataset's measured comparisons ran serially, without concurrent
test builds. These are warm-cache local measurements, not cold-I/O guarantees.

Both schemas expose identical records, including an identical original-size
column. Historical inputs lacking original sizes use zero in BOTH variants;
no full extent is guessed from an incomplete sample. Thus these measurements
isolate name normalization/joins, not the additional cost of storing genuine
original sizes in newly converted traces. Both databases were vacuumed before
comparison; pre-existing unused database space is not counted as a lookup saving.

Times are medians in seconds. `Query` fetches all view/table rows into Python;
`load` constructs the backend `Sampler`, including its chunked pandas read;
`load + lifetimes` additionally pairs allocations/frees. Hash calculation is
outside the timed interval. These stages overlap and must not be added together.

| Input | Stage | Repeated text | Name lookups | Change |
| --- | --- | ---: | ---: | ---: |
| Valkey | Query | 0.856 | 0.903 | +5.5% |
| Valkey | Load | 1.552 | 1.600 | +3.1% |
| Valkey | Load + lifetimes | 2.264 | 2.302 | +1.7% |
| BCCO | Query | 0.803 | 0.824 | +2.7% |
| BCCO | Load | 1.483 | 1.516 | +2.2% |
| BCCO | Load + lifetimes | 2.037 | 2.069 | +1.6% |

| Input | Repeated text (bytes) | Name lookups (bytes) | Reduction |
| --- | ---: | ---: | ---: |
| Valkey | 54,403,072 | 44,965,888 | 17.3% |
| BCCO | 67,690,496 | 47,890,432 | 29.3% |

Every paired query, loaded dataframe, and lifetime dataframe had equal row
counts and hashes. Peak process RSS was essentially unchanged: the view still
expands strings before pandas receives them. The benefit demonstrated here is
database size, with a small measured read-time penalty, not faster loading or
lower backend memory. These joins are not executed by the browser on timeline
movement or page selection.

Raw trials: [Valkey](event-schema-valkey-results-20260929.json),
[BCCO](event-schema-bcco-results-20260929.json).
Reproduction script: [benchmark_event_schema.py](benchmark_event_schema.py).
For example, inside the artifact Python environment:

```bash
python3 research/camera-ready/benchmark_event_schema.py \
  --input /path/to/retained.sqlite --out /path/to/new-private-study
```

The script reads the input through a read-only connection and refuses an existing
output directory. It produces copies for the comparison, never modifies the input,
and checks equality after every timed trial.

## Validation

Final Python suite: 96 tests run, 95 passed, one existing skip because the
SetBench record-manager submodule is not initialized in this worktree. Adjacent
current-bucket, detail-selection, and snapshot-export TypeScript tests also pass.

- Native conversion, original extents through sampling and frees, address reuse,
  regeneration over both old-table and new-view databases, backend lifetime and
  page payloads, old-database reading, exporter sizes, and equal cache metrics.
- Strict TypeScript helper checks: first/middle/last fragments, exact endings,
  unknown extents, live-time/type filtering, 4-KiB and 2-MiB pages.
- Actual React page-card components and Sass rendered into browser fixtures;
  normal pages, huge-page overview, and zoomed huge pages inspected in Edge.
  Marker counts and pointer-event transparency checked. This is a focused
  component/browser check, not an exhaustive interactive application test.

Test commands:

```bash
python3 -m unittest discover -s artifact/tests
node artifact/tests/test_continuation_edges.cjs
```

The repository's pre-existing production-build/type-cleanup work remains separate.
