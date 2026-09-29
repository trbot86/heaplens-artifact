"""Compact summary from retained-input coverage and local browser evidence."""
import argparse
import json
from pathlib import Path
import statistics

ap = argparse.ArgumentParser()
ap.add_argument('evidence', type=Path); ap.add_argument('--out', type=Path, required=True)
args = ap.parse_args()
cases = []
for file in sorted(args.evidence.glob('*/results.json')):
    data = json.loads(file.read_text())
    rows = []
    for cap in (None, 25000, 50000, 100000):
        trials = [r for r in data['trials'] if r['cap'] == cap]
        row = dict(record_budget=cap, trials=len(trials),
            all_clusters=sum(not r['omitted_clusters'] for r in trials),
            all_types=sum(not r['omitted_types'] for r in trials),
            selected_pages_range=[min(r['selected_pages'] for r in trials), max(r['selected_pages'] for r in trials)],
            selected_records_range=[min(r['selected_records'] for r in trials), max(r['selected_records'] for r in trials)],
            selection_ms_median=statistics.median(r['seconds']*1000 for r in trials))
        if data['name'] == 'valkey-full':
            row['genuine_rax_successes'] = sum(r['rax_genuine_objects'] > 0 for r in trials)
        rows.append(row)
    cases.append(dict(name=data['name'], page_size=data['page_size'],
                      max_page_records=data['max_page_records'], results=rows))
browser = [json.loads(line) for line in (args.evidence/'browser.jsonl').read_text().splitlines()]
stress = []
for records in (50000, 100000, 250000):
    for kind in ('live', 'churn'):
        trials = [r for r in browser if r['records'] == records and r['kind'] == kind]
        if not trials:
            continue
        # Ordinary per-trial medians, then median across trials.
        responses = [[e['ms'] for e in r['metrics']['events'] if e['kind']=='response'
                      and e['action']=='slider' and e['type']=='pointermove'] for r in trials]
        stress.append(dict(records=records, kind=kind, trials=len(trials),
            transport=sorted({r.get('transport', 'playwright-route') for r in trials}),
            ready_ms_median=statistics.median(r['metrics']['ready']['ms'] for r in trials),
            slider_proxy_ms_median=statistics.median(statistics.median(v) for v in responses),
            slider_proxy_ms_max=max(max(v) for v in responses),
            errors=sum(len(r['errors']) for r in trials)))
out = dict(page_budget=128, coverage=cases, browser_stress=stress,
    browser_scope='128 two-MiB rows; synthetic live/churn histories; fixed real cache/statistics payload; no dense full-page zoom claim',
    response_metric='input-handler entry to second requestAnimationFrame, not paint latency or FPS')
args.out.write_text(json.dumps(out, indent=2)+'\n')
