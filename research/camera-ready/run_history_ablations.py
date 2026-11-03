"""Use the cache campaign's frozen inputs with fixed representative page IDs."""
import argparse
import json
from pathlib import Path
import shutil
import time
from run_processing_ablations import bounded_docker, digest

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--study',type=Path,required=True)
ap.add_argument('--source',type=Path,required=True)
args=ap.parse_args()
script='research/camera-ready/ablate_histories.py'
shutil.copy2(args.source/script,args.study/'candidate'/script)
(args.study/'evidence/history-source.json').write_text(json.dumps({script:digest(args.source/script)},indent=2))
base=['python3','/candidate/'+script,'--root','/candidate']
results=[]
started=time.monotonic()
for name,page in [('valkey',4096),('bcco',2097152)]:
    common=base+['--database',f'/inputs/{name}.sqlite','--page-size',str(page)]
    plan=f'/evidence/history-{name}-plan.json'
    label=f'history-{name}-warmup'
    outcome=bounded_docker(args.study,label,common+['--policy','reduced','--make-plan',plan,
                           '--output',f'/evidence/{label}.json'])
    assert outcome['exit_code']==0,label
    expected_cache=None
    for rep in range(3):
        for policy in (['reduced','full'] if rep%2==0 else ['full','reduced']):
            if time.monotonic()-started>1200:
                raise TimeoutError('20-minute history campaign budget reached')
            label=f'history-{name}-{policy}-{rep}'
            extra=['--payload',f'/evidence/history-{name}-{policy}-payload.json'] if rep==0 else []
            outcome=bounded_docker(args.study,label,common+['--policy',policy,'--plan',plan,
                            '--output',f'/evidence/{label}.json',*extra])
            assert outcome['exit_code']==0,label
            row=json.loads((args.study/'evidence'/(label+'.json')).read_text())
            if expected_cache is None: expected_cache=row['cache_sha256']
            assert row['cache_sha256']==expected_cache, 'Unrelated cache output changed'
            row.update(case=name,rep=rep)
            results.append(row)
            (args.study/'evidence/history-results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({'history_complete':True,'trials':len(results),'fixed_clusters_and_cache_verified':True}),flush=True)
