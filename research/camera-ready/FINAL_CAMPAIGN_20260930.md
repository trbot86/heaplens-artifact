# Final CR campaign, September 30

User-authorized integration and final-measurement campaign, Pyke only for
application timings. Evaluator main remains unchanged. All source snapshots,
submodules, commands, image identity, raw outputs and failures are retained.
Do not pool earlier measurements with this campaign or extend trial counts
based on observed improvements.

## Fixed sequence

1. Regression checks and small HNSW factor smokes.
2. HNSW layout/huge-page 2x2: 128 D and 1536 D, ten blocks each (80 processes).
3. HNSW packed/separated-offset-32/separated-aligned: both dimensions,
   six balanced-order blocks each (36 processes).
4. Gate on successful final CR sampling matrix: five p/s configurations,
   twenty seeds each, plus twenty EFRB representative-selection trials.
5. Nine full-size comparisons using the artifact's agreed defaults, ten
   repetitions per variant; both HNSW dimensions. TPC-C additionally enables
   `HEAPLENS_CR_FULL_FACTORS=1` in the container environment: BCCO lock-only
   and combined-plus-shared-reclaimer, EFRB padding-only and shared-reclaimer-only
   with mimalloc and tree segregation held fixed. No implementation of a new
   application optimization is introduced.
6. Stock-logger overhead: three trees, two update rates, two arms, ten
   repetitions (120 trials). This command does not include the separate
   wait-probe instrumentation, which needs a separately matched confirmation.

HNSW uses 1M vectors, 100K indexed queries, 10K warmup, five query iterations,
M=16, ef_construction=200, ef=64, k=10, 24 physical node-0 cores and local
memory, system libc; construction and query thread counts both 24. The
alignment-control source differs from corrected source only in its existing
vector-owner/offset control. All three alignment arms use that same control
source. Do not claim the offset-32 comparison measures arbitrary separation.

The final sampling matrix rebuilds the converter from the frozen CR sources,
uses its supported sampling seed, preserves the five existing p/s pairs
(0.001/1, 0.01/1, 0.1/1, 0.1/2, 1/1), and explicitly passes the GUI defaults
128 pages/100,000 prepared records. It scores the existing verified raxNode
identities and robj predicate, not an LLM judgment or a changed target.

## Operational boundaries

Fresh local scratch on Pyke; no Jax/Rift compute. Hold the shared Pyke experiment
lock, refuse concurrent containers or substantial unrelated load, serialize
all builds/timings and stop on failures. Retain results, do not delete prior
campaign data. Check disk space between stages. Record perf availability;
never reinterpret missing counters as zero. No public push is part of this run.
The complete campaign can take substantially longer than the user's absence.

The following are not automatically covered by the numerical umbrella:
whole-program versus timed-loop logging accounting, wait-probe confirmation,
HNSW query-window PMU attribution, repeated local processing/UI ablations,
or fresh LLM sessions. Track these separately rather than marking all CR
evaluation complete when the umbrella finishes.
