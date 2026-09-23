# Optional LLM-guided Valkey exercise

The core artifact does **not** need an LLM subscription, API key, or model call.
Saved inputs and the final patch make its diagnosis and optimization auditable.
Fresh LLM exploration is optional and nondeterministic; it is not expected
to rediscover the identical patch or numerical result.

## Recorded path: no model access needed

1. Read `data/valkey/v2_export/compact/` and
   `data/valkey/v2_export/heaplens_analysis.txt`. These are the historical
   compact snapshots and their accompanying summary. Type aliases map to
   concrete type names; addresses, sizes, lifetimes, page/cluster membership,
   and cache-line boundaries provide the observations.
2. Compare with `historical/valkey/recommendations.md`, then inspect
   `patches/valkey-B1C1_64.patch`. This is a saved outcome, not evidence that
   every model will discover it.
3. Run `bash artifact/run.sh valkey --profile smoke`. The driver builds
   pristine saved baseline and patched sources separately, preloads synthetic
   data, and measures each without HeapLENS logging.
4. On the required dual-NUMA hardware, use `--profile paper` for ten runs of
   each variant. Inspect the raw memtier JSON, not only the summary. Read
   `PROVENANCE.md` before comparing fresh measurements with historical ones.

To exercise the exporter itself:

```bash
bash artifact/run.sh export
```

The printed results directory contains regenerated raw, compact, and analysis
text. Clustering/resampling is nondeterministic, so representative pages and
cluster IDs need not exactly match the saved export.

## Fresh exploration: keep the answer out of the input

Use a new isolated workspace with **only** these inputs:

- A copy of `vendor/valkey/` as `valkey/` (no `.git`, previous model sessions,
  recommendations, optimized code, or historical results).
- The supplied compact snapshots and type/field legends from
  `data/valkey/v2_export/compact/`, plus the accompanying analysis text.
- The neutral workload description below and, optionally, the paper's tool
  explanation with application-optimization results removed.

Do not mount the complete artifact into an agent sandbox intended to test
independent discovery: it contains the answer. A separate directory alone is
not a security boundary if the agent can read its parent directories. For a
controlled comparison use separate isolated environments with equal budgets,
the same source/workload, and only the HeapLENS input varied. Keep agent
credentials outside the artifact and do not include chat/account files in a
release. No new guided-versus-unguided comparison is claimed by this exercise.

The historical study used Codex with GPT-5.5, extra-high reasoning. If that
model is unavailable, record the actual model/version and reasoning setting;
do not label a run with a newer model as an exact repetition of the study.

## Suggested prompts (new demonstration protocol)

These prompts are evaluator instructions, not a claimed verbatim historical
transcript. Use a single new session for the following stages to retain the
model's analysis between prompts. Do not show recommendations or the saved
patch until exploration is complete.

**1. Diagnose, without editing.**

> This workspace contains Valkey source and HeapLENS observations from a
> synthetic string-cache preload. The performance workload uses 128-byte
> values, 4 million keys, 20% SET and 80% GET, 24 server I/O threads and
> 24 memtier threads on separate NUMA nodes, 4 clients per thread, pipeline
> depth 16, TCP loopback, and disabled persistence. The diagnostic trace
> contains a 1-million-key preload; do not confuse its scale with the
> throughput workload. Inspect the observations and relevant source. Report
> concrete memory-layout hypotheses with supporting pages/types/offsets,
> explain uncertainty, and distinguish modeled layout from measured cache
> behavior. Do not modify code yet.

**2. Propose bounded changes.**

> Propose a small number of localized allocation or object-layout changes
> motivated by that report. Preserve command behavior, object ownership,
> lifetime, persistence/network formats, and public/module interfaces.
> Explain memory-footprint costs and likely failure modes. Do not pursue a
> cross-cutting string-embedding redesign. Recommend which hypothesis to
> test first, without looking for prior solutions elsewhere.

**3. Implement and verify.**

> Implement the selected localized change in a separate candidate copy.
> Preserve the baseline. Check allocation/free/reallocation pairs and run
> applicable tests. Supply a diff and exact build instructions. Do not claim
> a speedup from a smoke run; request an independent, repeated baseline versus
> candidate benchmark using the fixed workload before drawing a conclusion.

An interactive Codex session is convenient. For scripting, official
[non-interactive documentation](https://developers.openai.com/codex/noninteractive/)
describes `codex exec` and `codex exec resume`; reuse the explicit session ID
for later stages. `--ephemeral` prevents saved session files and is unsuitable
when relying on later resumption; it is not a general promise of memory or
filesystem isolation. Confirm flags against your installed CLI. This artifact
does not install Codex or initiate paid model calls.
