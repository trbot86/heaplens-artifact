"""Derive compact timing summaries from paired backend/browser observations."""
import argparse, json
from pathlib import Path
from statistics import median

ap=argparse.ArgumentParser();ap.add_argument('evidence',type=Path);ap.add_argument('--out',type=Path,required=True)
ap.add_argument('--browser-prefix',default='')
a=ap.parse_args();backend=[]
for case in ('valkey-full','tpcc-bcco-2m'):
    data=json.loads((a.evidence/case/'backend.json').read_text())
    summary={}
    for policy in ('baseline','optimized'):
        rows=[r for r in data['rows'] if r['policy']==policy]
        summary[policy]=dict(n=len(rows),total_seconds=median(r['total_seconds'] for r in rows),
            total_seconds_raw=[r['total_seconds'] for r in rows],
            cache_seconds=median(r['phases']['cache'] for r in rows))
    backend.append(dict(case=case,complete_payload_equal=data['complete_payload_equal'],summary=summary))
browser=[json.loads(line) for line in (a.evidence/(a.browser_prefix+'browser.jsonl')).read_text().splitlines()]
for row in browser:
    events=row['metrics']['events'];actions={}
    for e in events:
        if e['kind']!='response':continue
        name=e['action'];kind=None
        if name.startswith('slider-') and e['type']=='pointermove':
            down=[x['start'] for x in events if x['kind']=='response' and x['action']==name and x['type']=='pointerdown']
            up=[x['start'] for x in events if x['kind']=='response' and x['action']==name and x['type']=='pointerup']
            if down and up and min(down)<=e['start']<=max(up):kind='slider_drag'
        elif name.startswith('page-visibility-') and e['type']=='click':kind='page_visibility'
        elif name.startswith('cache-visibility-') and e['type']=='click':kind='cache_visibility'
        elif name in ('filter','clear-filter') and e['type']=='input':kind='type_filter'
        elif name=='scroll' and e['type']=='wheel':kind='scroll'
        if kind:actions.setdefault(kind,[]).append(e['ms'])
    row['action_ms']={k:dict(n=len(v),median=median(v),maximum=max(v),raw=v) for k,v in actions.items()}
summaries=[]
for case,budget in sorted({(r['name'],r['budget']) for r in browser}):
    result=dict(case=case,budget=budget,policies={})
    for policy in ('baseline','optimized'):
        group=[r for r in browser if r['name']==case and r['budget']==budget and r['policy']==policy]
        ready=[r['metrics']['ready']['ms'] for r in group]
        acts={}
        for kind in ('slider_drag','page_visibility','cache_visibility','type_filter','scroll'):
            values=[r['action_ms'][kind]['median'] for r in group]
            acts[kind]=dict(median_of_trial_medians_ms=median(values),trial_medians_ms=values,
                samples_per_trial=[r['action_ms'][kind]['n'] for r in group])
        result['policies'][policy]=dict(n=len(group),ready_median_ms=median(ready),ready_raw_ms=ready,actions=acts)
    summaries.append(result)
equality=json.loads((a.evidence/(a.browser_prefix+'browser-equality.json')).read_text())
out=dict(baseline_commit='e45d924',backend=backend,browser=summaries,equality=equality,
         browser_version=browser[0]['browser'],
         scope='Three paired trials per input. Browser replay excludes backend preparation. Interaction metric is input-handler entry to second animation frame, not compositor-present latency.')
a.out.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
