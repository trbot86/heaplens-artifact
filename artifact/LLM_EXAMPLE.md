# LLM-guided Valkey analysis and optimization

The saved inputs and optimization patch can be examined without model access.
Fresh LLM exploration is optional and nondeterministic.

In the paper, Codex used HeapLENS's human-facing instructions to instrument
Valkey and HNSWLib, including custom-allocator handling, collect allocation
traces, and export data for analysis. The prompts below document this workflow,
as well as the subsequent analysis and optimization stages.

## Examine the recorded Valkey example

1. Read `data/valkey/v2_export/compact/` and
   `data/valkey/v2_export/heaplens_analysis.txt`. These are the compact page
   snapshots and accompanying analysis. The legends identify object types;
   the snapshots show addresses, sizes, lifetimes, page/cluster membership,
   and cache-line boundaries.
2. Read `historical/valkey/recommendations.md`, then inspect
   `patches/valkey-B1C1_64.patch` for the resulting allocation-placement changes.
3. Build and run a small baseline/optimized comparison:

   ```bash
   bash artifact/run.sh valkey --profile smoke
   ```

4. For the full performance comparison, use a machine with two NUMA nodes
   and 24 available physical cores per node:

   ```bash
   HEAPLENS_NUMA=1 bash artifact/run.sh valkey --profile paper
   ```

   This runs ten trials of each variant with 4M keys, 128-byte values,
   20% SET/80% GET, and 30-second measurement phases. Results are written to
   `artifact/results/valkey-<timestamp>/`. `summary.json` reports mean
   throughput and the percentage change; each variant's `*-repN/` directory
   contains its `benchmark.json` with throughput, latency, and error counts.

To regenerate the text export from the supplied SQLite trace:

```bash
bash artifact/run.sh export
```

For an interactive investigation, the GUI's **Export 5 snapshots** button saves
the selected representative pages as `page_layout_snapshots.txt`; it does not
download automatically on loading. This simpler GUI export is separate from
the raw/compact command-line export used below, whose protocol is unchanged.

The printed results directory contains raw snapshots, compact snapshots,
and analysis text. Representative pages and cluster IDs can change when
the trace is resampled.

## Workspace and session setup

Appendix D's “LLM experiment methodology” describes three separate workspaces:

| Workspace | Contents and purpose |
|---|---|
| R1: instrumentation | Application source, `benchmark.py`, HeapLENS source, and a copy of the paper with all LLM-related content removed; generate the allocation trace and text export. |
| R2: analysis with HeapLENS | Uninstrumented application source and `benchmark.py`, plus the exported text and the same tool-only paper; diagnose, recommend changes, implement and benchmark them. |
| R3: analysis without HeapLENS | Uninstrumented application source and `benchmark.py`; perform the comparison without HeapLENS data or the paper. |

Use a fresh, isolated Codex instance with no prior chat history in each
workspace. Exclude the artifact's saved recommendations, optimized patch,
and historical performance results from the agent's accessible files.
`vendor/valkey/` supplies the baseline source. The original Valkey benchmark
script is retained in `historical/valkey/benchmark.py`; it refers to the
original Docker/directory layout, whereas the commands above use the packaged
runner. Set up the benchmark and its dependencies before starting the agent.

Disable Codex memory for every session, including both memory reuse and
generation. With the documented CLI settings:

```bash
codex -c features.memories=false \
      -c memories.use_memories=false \
      -c memories.generate_memories=false
```

These are per-invocation overrides; use them again when starting each fresh
session.

## Prompts from the paper

The six prompt blocks below reproduce the wording in Appendix D, with LaTeX
formatting removed. `sifter` is HeapLENS's internal directory name;
`heaplens.pdf` means the paper copy with all LLM-related content removed.
Replace `{PATH}` with the export location, arranging the analysis file and
compact `heaplens_output*` files together there. Other paths refer to the
workspace layout described above.

### 1. R1: instrument the application

Start a new chat in R1.

```text
Integrate heaplens according to sifter/README.md and sifter.sh, noting heaplens.pdf as background. Use the existing docker workflow to avoid dependency issues. Use sifter's built-in sampling, but try to limit runs to sizes that will produce <= ~5GB databases before sampling. Where custom allocators are used, augment the instrumentation with semantic type information. We should also use the visualization exporter that produces text from the sqlite database and the react frontend.
```

### 2. R1: run and export

Continue the instrumentation chat with this prompt. Copy the generated text
and tool-only paper into R2 when this stage finishes.

```text
Let's run the benchmark in this folder, then use the visualization exporter that
produces text from the sqlite database and the react frontend. Use the existing
docker workflow.
```

### 3. R2: analyze the HeapLENS data

Start a new chat in R2.

```text
We would like to identify memory layout problems/anomalies in this project.
Produce a report summarizing the problems found, if any, highlighting specific
layout problems, grouped by type (output to: report.md). In addition to finding
what you can by code inspection, read the HeapLENS paper (heaplens.pdf) with an
emphasis on understanding the specific memory layout issues that can be found
using the data HeapLENS makes available. Analyze the data from
{PATH}/heaplens_analysis.txt and
{PATH}/heaplens_output*. Type aliases in the report data should be
expanded to human readable form, which could mean a reasonable short form for
long type names. The entrypoint is benchmark.py with jemalloc. Don't use
resources outside of this directory tree (unless explicitly asked to).
```

### 4. R2: recommend improvements

Start a new chat in R2, retaining `report.md` from the preceding stage.

```text
Look at the report and recommend a sequence of memory layout improvements
suitable for progressive A/B testing and factor analysis, and save these
recommendations as recommendations.md.
```

### 5. R2: implement and benchmark

Start another new chat in R2, retaining the report and recommendations.

```text
Implement the recommendation sequence and use the included benchmark to judge
improvements.
```

### 6. R3: analyze without HeapLENS

For the no-HeapLENS comparison, start a new chat in R3 and use this analysis
prompt instead of step 3. Then repeat steps 4 and 5 in fresh R3 chats using
the report and recommendations generated there.

```text
We would like to identify memory layout problems/anomalies in this project.
Produce a report summarizing the problems found, if any, highlighting specific
layout problems, grouped by type (output to: report.md). The entrypoint is
benchmark.py. Don't use resources outside of this directory tree (unless
explicitly asked to).
```

The paper also records occasional continuation prompts, such as
`continue the investigation`, and follow-ups when the unguided agent pursued
a cross-cutting string-embedding redesign, for example:
`suppose we can't do embedding. implement and A/B test your other suggestions that aren't massive sweeping changes.`
That was an interactive follow-up, not a restriction added to the initial
analysis or recommendation prompts.
