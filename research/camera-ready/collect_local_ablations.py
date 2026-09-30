"""Collect compact evidence, excluding database/payload/binary build products."""
import argparse
import json
from pathlib import Path
import shutil
import statistics as st
import subprocess

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--study',type=Path,required=True)
ap.add_argument('--workspace',type=Path,required=True)
args=ap.parse_args()
src=args.study/'evidence'
out=args.workspace/'artifact-tools/processing-ablation-20260929'
out.mkdir(exist_ok=False)
for p in src.iterdir():
    if p.suffix in ('.json','.jsonl','.log','.sha256') and '-payload' not in p.name:
        shutil.copy2(p,out/p.name)
subprocess.run(['tar','-czf',str(out/'source-snapshot.tar.gz'),'-C',str(args.study),'candidate'],check=True)
def read(name):return json.loads((out/name).read_text())
def stats(values):return dict(median=st.median(values),minimum=min(values),maximum=max(values))
def groups(rows,fields,policies):
    result=[]
    for case in dict.fromkeys(r.get('case','valkey') for r in rows):
        for policy in policies:
            rr=[r for r in rows if r.get('case','valkey')==case and r['policy']==policy and r['rep']>=0]
            assert len(rr)==3,(case,policy,len(rr))
            value=dict(case=case,policy=policy,trials=len(rr))
            for field in fields:
                value[field]=stats([r[field] for r in rr])
            if 'phases' in rr[0]:
                value['phases']={p:stats([r['phases'][p] for r in rr]) for p in rr[0]['phases']}
            result.append(value)
    return result
summary=dict(
    cache=groups(read('results.json'),['total_seconds','peak_rss_kib','payload_bytes'],['prefix','direct']),
    history=groups(read('history-results.json'),['total_seconds','peak_rss_kib','payload_bytes',
                 'selected_pages','selected_records','all_prepared_objects','all_display_histories'],['reduced','full']),
    native=groups(read('native-results.json'),['conversion_seconds','peak_native_rss_kib','database_bytes'],['prefix','direct']),
)
life=out/'lifetime-spans.json'
if life.exists():summary['lifetimes']=read('lifetime-spans.json')
browser=args.workspace/'artifact-tools/history-load-ablation-20260929/browser.jsonl'
if browser.exists():
    rows=[json.loads(line) for line in browser.read_text().splitlines()]
    summary['database_to_ui']=[]
    for name in ('valkey','tpcc-bcco-2m'):
        for policy in ('reduced','full'):
            rr=[r for r in rows if r['name']==name and r['policy']==policy and r['rep']>=0]
            assert len(rr)==3 and all(r['status']=='complete' and r['cleanup'] and not r['errors'] for r in rr)
            summary['database_to_ui'].append(dict(case=name,policy=policy,trials=len(rr),
                ready_ms=stats([r['ready']['ms'] for r in rr]),
                post_ready_heap_bytes=stats([r['post_ready_heap_bytes'] for r in rr])))
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
compact=args.workspace/'artifact-camera-ready/research/camera-ready/processing-ablation-results-20260929.json'
compact.write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
