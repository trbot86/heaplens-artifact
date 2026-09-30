"""Run a bounded, serialized local 2x2 with immutable source/input snapshots."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time
from run_processing_ablations import bounded_docker, digest

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--workspace',type=Path,required=True)
ap.add_argument('--study',type=Path,required=True)
args=ap.parse_args()
study=args.study
source=args.workspace/'artifact-camera-ready'
study.mkdir(exist_ok=False)
(study/'evidence').mkdir()
(study/'inputs').mkdir()
shutil.copytree(source/'sifter_vis_d3/server',study/'candidate/sifter_vis_d3/server',ignore=shutil.ignore_patterns('__pycache__'))
research=study/'candidate/research/camera-ready'
research.mkdir(parents=True)
for name in ('ablate_cache_prefix.py','ablate_backend_matrix.py','run_backend_matrix.py','run_processing_ablations.py'):
    shutil.copy2(source/'research/camera-ready'/name,research/name)
old=Path('/tmp/heaplens-processing-ablation-20260929/inputs')
for name in ('valkey','bcco'):
    shutil.copy2(old/(name+'.sqlite'),study/'inputs'/(name+'.sqlite'))
manifest=dict(source={str(p.relative_to(study/'candidate')):digest(p) for p in (study/'candidate').rglob('*.py')},
    inputs={p.name:dict(bytes=p.stat().st_size,sha256=digest(p)) for p in (study/'inputs').iterdir()},
    image=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}','heaplens-atc26:submission'],text=True).strip(),
    buckets=2000,page_budget=128,record_budget=100000,seed=20260929,
    cpus=2,memory_gib=12,cache_seconds=150,worker_seconds=180,campaign_seconds=1800,
    protocol='One discarded warmup per cell; three interleaved trials per cell, rotating order; fresh worker per trial')
(study/'evidence/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
base=['python3','/candidate/research/camera-ready/ablate_backend_matrix.py','--root','/candidate']
assert bounded_docker(study,'self-test',base+['--self-test'],seconds=60)['exit_code']==0
started=time.monotonic()
rows=[]
cells=[('enumerated','direct'),('enumerated','prefix'),('range','prefix'),('range','direct')]
for case,page in [('valkey',4096),('bcco',2097152)]:
    expected=None
    for rep in (-1,0,1,2):
        shift=max(rep,0)
        order=cells[shift:]+cells[:shift]
        for spatial,policy in order:
            if time.monotonic()-started>1800:
                raise TimeoutError('Campaign budget reached')
            label=f'{case}-{spatial}-{policy}-{rep}'
            command=base+['--database',f'/inputs/{case}.sqlite','--page-size',str(page),
                '--spatial',spatial,'--policy',policy,'--output',f'/evidence/{label}.json']
            outcome=bounded_docker(study,label,command,seconds=180)
            if outcome['exit_code']:
                raise RuntimeError(f'Stopped at failed/censored cell {label}; see log')
            row=json.loads((study/'evidence'/(label+'.json')).read_text())
            if expected is None:expected=row['payload_sha256']
            assert row['payload_sha256']==expected,f'Full payload mismatch: {label}'
            row.update(case=case,rep=rep)
            rows.append(row)
            (study/'evidence/results.json').write_text(json.dumps(rows,indent=2)+'\n')
            print(json.dumps(dict(case=case,spatial=spatial,temporal=policy,rep=rep,cache=row['phases']['cache'],total=row['total_seconds'])),flush=True)
out=args.workspace/'artifact-tools/backend-matrix-20260929'
out.mkdir(exist_ok=False)
shutil.copytree(study/'evidence',out/'evidence')
subprocess.run(['tar','-czf',str(out/'source-snapshot.tar.gz'),'-C',str(study),'candidate'],check=True)
shutil.copy2(study/'evidence/results.json',source/'research/camera-ready/backend-matrix-results-20260929.json')
print('COMPLETE: all 32 payloads match within each input',flush=True)
