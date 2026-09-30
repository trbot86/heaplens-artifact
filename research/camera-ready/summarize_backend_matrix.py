"""Produce paper-ready tables from a complete, equality-checked backend matrix."""
import argparse
import json
from pathlib import Path
import statistics as st

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--results',type=Path,required=True)
ap.add_argument('--out',type=Path,required=True)
args=ap.parse_args()
rows=json.loads(args.results.read_text())
cells=[('enumerated','direct'),('range','direct'),('enumerated','prefix'),('range','prefix')]
summary=[]
for case in ('valkey','bcco'):
    allrows=[r for r in rows if r['case']==case]
    assert len(allrows)==16 and len({r['payload_sha256'] for r in allrows})==1
    for spatial,temporal in cells:
        rr=[r for r in allrows if r['spatial']==spatial and r['policy']==temporal and r['rep']>=0]
        assert len(rr)==3 and all(r['status']=='complete' for r in rr)
        entry=dict(case=case,spatial=spatial,temporal=temporal,n=3,
                   payload_sha256=rr[0]['payload_sha256'],selected_pages=rr[0]['selected_pages'],
                   selected_records=rr[0]['selected_records'])
        for key,values in [('cache',[r['phases']['cache'] for r in rr]),
                           ('total',[r['total_seconds'] for r in rr]),
                           ('rss_mib',[r['peak_rss_kib']/1024 for r in rr])]:
            entry[key]=dict(median=st.median(values),minimum=min(values),maximum=max(values),raw=values)
        summary.append(entry)
args.out.mkdir(exist_ok=True)
(args.out/'backend-matrix-summary-20260929.json').write_text(json.dumps(summary,indent=2)+'\n')
lookup={(r['case'],r['spatial'],r['temporal']):r for r in summary}
lines=['# Matched backend spatial-by-temporal ablation','',
       'September 29, 2026. All 32 runs completed: one discarded warmup and three',
       'interleaved measured trials per cell on each of two inputs. Complete prepared',
       'payload hashes match across all 16 runs within each input.','',
       '## Paper table','',
       '| Spatial range updates | Temporal prefix sums | Valkey cache / preparation (s) | BCCO cache / preparation (s) |',
       '| --- | --- | ---: | ---: |']
tex=[r'\begin{table}[t]',r'\centering',r'\small',r'\begin{tabular}{ccrr}',r'\hline',
     r'Range updates & Prefix sums & Valkey & BCCO \\',r'\hline']
for spatial,temporal in cells:
    enabled=['Yes' if spatial=='range' else 'No','Yes' if temporal=='prefix' else 'No']
    values=[]
    for case in ('valkey','bcco'):
        row=lookup[case,spatial,temporal]
        values.append(f"{row['cache']['median']:.2f} / {row['total']['median']:.2f}")
    lines.append('| '+' | '.join(enabled+values)+' |')
    tex.append(' & '.join(enabled+values)+r' \\')
caption=('Cache preparation / complete backend preparation in seconds; medians of three '
         'interleaved trials per variant. All variants use the same retained inputs, '
         '2,000 time buckets, 128-page and 100,000-history-record budgets, and fixed '
         'clustering seed. Complete preparation includes database reading, statistics, '
         'page preparation, cache preparation, and JSON serialization; it excludes HTTP '
         'and browser rendering. Output hashes match within each input.')
lines+=['','Caption: '+caption,'','## Interpretation','']
for case in ('valkey','bcco'):
    before=lookup[case,'enumerated','direct'];after=lookup[case,'range','prefix']
    lines.append(f"- {case}: enabling both techniques changes cache preparation from {before['cache']['median']:.3f} to {after['cache']['median']:.3f} s (baseline/optimized ratio {before['cache']['median']/after['cache']['median']:.2f}), and complete preparation from {before['total']['median']:.3f} to {after['total']['median']:.3f} s (ratio {before['total']['median']/after['total']['median']:.2f}). Ratios below one mean the optimized combination is slower.")
lines+=['', 'Compare rows within a fixed setting of the other factor to attribute an',
        'individual technique. Do not multiply speedups from different comparisons.',
        'In particular, examine range-only versus both on BCCO: short lifetimes can',
        'make direct temporal accumulation cheaper than prefix sums.','',
        '## Trial ranges and memory','',
        '| Input | Spatial / temporal | Cache min–max (s) | Preparation min–max (s) | Median peak RSS (MiB) |',
        '| --- | --- | ---: | ---: | ---: |']
for r in summary:
    lines.append(f"| {r['case']} | {r['spatial']} / {r['temporal']} | {r['cache']['minimum']:.3f}–{r['cache']['maximum']:.3f} | {r['total']['minimum']:.3f}–{r['total']['maximum']:.3f} | {r['rss_mib']['median']:.1f} |")
lines+=['','## Method and provenance','',
    'All cells use fresh isolated Linux workers on the local i7-14700KF/WSL2 host,',
    'two CPU equivalents, 12 GiB, and one BLAS/OpenMP thread. No GPU participates',
    'in this backend experiment. Cache geometry is 32 KiB, eight-way, with 64-byte',
    'lines; database page sizes are 4 KiB for Valkey and 2 MiB for BCCO. The seed',
    'is 20260929. Prepared history reduction, field expansion, reconstruction, and',
    'the complete output format are unchanged across cells. Sources and input',
    'hashes are frozen in the evidence manifest.','',
    'The enumerated reference uses NumPy add.at with repeated cache-set indices.',
    'Its direct-temporal form broadcasts updates across a NumPy lifetime slice;',
    'it has no Python loop over time buckets. Unlike the older spatial ablation,',
    'it omits redundant per-line bucket/type index arrays, so this is a streamlined',
    'reference rather than byte-for-byte historical code. The same helper is used',
    'with and without temporal prefix sums.','',
    'Self-tests include 1,000 random spatial comparisons and 503 temporal/oracle',
    'cases for each spatial helper. Full-payload equality also holds on both real',
    'inputs across every cell and repeat. Cache phases are limited to 150 s,',
    'workers to 180 s, and launching further trials to a 30-minute campaign.',
    'No measured trial was censored.','',
    'Raw results: [backend-matrix-results-20260929.json](backend-matrix-results-20260929.json).',
    'Summary: [backend-matrix-summary-20260929.json](backend-matrix-summary-20260929.json).',
    'LaTeX table: [backend-matrix-table.tex](backend-matrix-table.tex).',
    'Author-local frozen sources, controller records, manifests, and trial logs:',
    '`artifact-tools/backend-matrix-20260929/` in the parent workspace.','',
    'See [paper prose and interface table](PAPER_PROCESSING_OPTIMIZATIONS.md). Earlier',
    'standalone ablations remain preserved; this matched matrix supersedes them',
    'for joint spatial/temporal attribution.']
tex += [r'\hline',r'\end{tabular}',r'\caption{'+caption+'}',r'\label{tab:heaplens-backend-ablation}',r'\end{table}']
(args.out/'BACKEND_MATRIX_RESULTS.md').write_text('\n'.join(lines)+'\n')
(args.out/'backend-matrix-table.tex').write_text('\n'.join(tex)+'\n')
print('\n'.join(lines[:28]))
