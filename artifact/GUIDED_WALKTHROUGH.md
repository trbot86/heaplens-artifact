# Guided HeapLENS use

## Start with a retained real-application trace

This route needs no cluster, perf access, LLM account, or instrumented rebuild.
It uses the Valkey trace that informed the paper's LLM-assisted investigation.

```bash
bash artifact/run.sh gui
```

Open <http://localhost:3000> in a desktop browser. Select
`valkey-artifact.sqlite`. Allow the initial clustering/precomputation to finish.
The GUI is intended for a wide desktop window; resize or zoom out if panels
are cramped. Both services are exposed only on the host's loopback interface.
Stop with Ctrl-C. Do not expose the research development server publicly.

1. **Choose a populated time.** The timeline initially selects the beginning
   of the trace, when many pages are empty. Drag its small circular time handle
   from the far left toward the right, after the growing allocation curves
   have flattened. This is a preload trace, approximately 4.3 seconds long.
2. **Identify the dominant allocation stream.** In the lower-right type table,
   `robj` is the dominant type, with roughly one million recorded allocations.
   `raxNode` is another stream relevant to the eventual patch. Colors identify
   types, not severity. Type colors and cluster IDs can change between samples.
3. **Read a page, not just its density.** The top-left bars are representative
   pages. Click a populated bar to inspect that page in the adjacent enlarged
   view: each row spans a cache line, and the horizontal scale is bytes.
   Repeated object boundaries reveal how objects pack and whether they cross
   cache-line boundaries. Compare pages dominated by the same type rather
   than treating equal fill density as equal layout.
4. **Connect panels.** The right-hand cache-set heatmap summarizes modeled
   address-to-set occupancy for the selected objects/time and cache geometry.
   It is not measured cache misses or proof of false sharing. The type table,
   page layout, and time selection supply context for the pattern. The flame
   and HITM controls require corresponding perf data; this trace does not
   supply it, so leave those controls off.
5. **Ask a testable optimization question.** Would placing the frequently
   allocated small object headers differently reduce unfavorable sharing or
   crossings without changing application semantics? A layout observation
   motivates that hypothesis; a separate uninstrumented benchmark tests it.
   Inspect `patches/valkey-B1C1_64.patch` only after forming your hypothesis.
   It cache-line-aligns selected small `robj` and radix-tree allocations and
   preserves allocation/free/reallocation behavior. It also increases memory
   use: higher throughput alone is not a complete optimization assessment.
6. **Close the loop.** Run `bash artifact/run.sh history` to inspect the
   retained results, or `bash artifact/run.sh valkey --profile smoke` to
   compile both variants and run a small functionality test. Use the paper
   profile on suitable hardware for a meaningful throughput comparison.

The `ADDRESS` / `CLUSTER` controls change page ordering. Small bars beside
page labels show a cluster's weight. The page pane scrolls: a partly visible
bar at its lower edge is not an additional special object or category.
`Settings` exposes visualization/clustering choices and cache geometry;
`Resample` selects a new representative view. Missing a pattern in one view
does not prove its absence. The supplied SQLite database and exporter allow
independent inspection of the retained data.

## EFRB: a simpler, higher-contrast teaching example

The package includes `efrb-smoke.sqlite`, a newly generated small trace.
Select it in the GUI; no new build is needed. This demonstrates the kind of
cache-set-underutilization diagnosis in the paper, not an exact reproduction
of the paper's screenshot, addresses, cluster numbers, or performance result.

1. Drag the timeline handle to about two seconds, after prefill. The legend
   lists 12,291 `node_t` allocations and 4,096 `info_t` allocations.
2. Select a densely populated page from the dominant cluster. Its adjacent
   cache-line view shows a regular pattern of three node lines followed by
   a descriptor line. Colors vary; use the legend to identify them.
3. Click the small chevron at the upper-left of the type legend to expose
   three visibility checkboxes per type: timeline, pages, cache.
4. Right-click the **third checkbox** on the `node_t` row, and select
   **Only this type**. Leave page visibility unchanged so both types remain
   visible in the page view.
5. With L1 selected, the saved small trace shows repeating groups of one
   empty set and three occupied sets for nodes. This is the key observation:
   apparently full pages do not imply uniform use of cache sets by a type.
   Including descriptors in the heatmap conceals the imbalance. These are
   modeled address occupancies, not measured miss counts.
6. This suggests separating node and descriptor allocation streams, or
   perturbing the regular allocation order. The four-variant performance
   driver below tests those hypotheses independently of instrumentation.

To generate your own small trace:

```bash
bash artifact/run.sh legacy ascylib_efrb --profile smoke
```

The output is `artifact/experiments/ascylib_efrb/ascylib_efrb.sqlite`. Copy it
into `sifter_vis_d3/`, return to the GUI selection page, and select it. The
paper-size profile uses a 2^18-key tree. Do not expect identical addresses,
cluster IDs, or speedups from a fresh small run.

The corresponding uninstrumented four-variant experiment is:

```bash
bash artifact/run.sh legacy ascylib_efrb_bench --profile paper
```

It compares the baseline, descriptor/node segregation, multithreaded prefill,
and their combination. See `VALIDATION.md` for what has actually been tested.
