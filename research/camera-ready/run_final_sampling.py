"""Final CR p/s matrix; frozen genuine rax identities and existing robj oracle."""
import gc
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
sys.path.insert(0, '/author-tools')
import sampling_layout_study as common
import rax_sampling_study as rare

ROOT=Path('/root/sifter'); OUT=Path('/evidence'); WORK=Path('/work')
RAW=Path('/retained/valkey-original')
class FinalSampler(common.Sampler):
    def get_sample_of_pages(self, *args, **kw):
        kw.update(page_budget=128, record_budget=100000)
        return super().get_sample_of_pages(*args, **kw)
common.Sampler=FinalSampler

def main():
    rare.selftest()
    OUT.mkdir(parents=True,exist_ok=True); WORK.mkdir(parents=True,exist_ok=True)
    assert not (OUT/'protocol.json').exists()
    rawsha=common.sha(RAW/'binary_dump.txt')
    original=json.loads(Path('/author-tools/rax-sampling-20260928/execution-protocol.json').read_text())
    assert rawsha==original['binary_log_sha256']
    ref=json.loads(Path('/author-tools/rax-sampling-20260928/lifetime-audit.json').read_text())
    build=['g++','-std=c++17','-O1',*map(str,sorted((ROOT/'type_analysis/convert_to_db').glob('*.cpp'))),
           '-lsqlite3','-lpthread','-ltbb','-o',str(WORK/'convert')]
    subprocess.run(build,check=True)
    settings=[(.001,1),(.01,1),(.1,1),(.1,2),(1.,1)]
    common.save(OUT/'protocol.json',dict(source_revision=os.environ['CR_REVISION'],
        raw_sha256=rawsha,converter_sha256=common.sha(WORK/'convert'),build=build,
        page_budget=128,record_budget=100000,native_buckets=3000,gui_buckets=2000,
        settings=settings,repetitions=20,seeds=list(range(20260928,20260948)),
        oracle_sha256=common.sha('/author-tools/rax-sampling-20260928/lifetime-audit.json'),
        scoring_script_sha256={p:common.sha('/author-tools/'+p) for p in ['sampling_layout_study.py','rax_sampling_study.py']}))
    def convert(label,p,s,seed):
        folder=OUT/label;folder.mkdir(); work=WORK/label;work.mkdir()
        for name in ['binary_dump.txt','typeset_dump.txt','fileset_dump.txt']:
            shutil.copy2(RAW/name,work/name)
        cmd=[str(WORK/'convert'),'--sample',str(p),'--num-pages-per-type',str(s),
             '--seed',str(seed),'--num-buckets','3000']
        with (folder/'converter.log').open('x') as log:
            subprocess.run(cmd,cwd=work,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        assert common.sha(work/'binary_dump.txt')==rawsha
        common.save(folder/'command.json',cmd)
        return folder,work/'allocs.sqlite'
    _,full=convert('reference',1,1,20260928)
    reference=common.make_reference('valkey',full,OUT/'robj-reference.json')
    assert reference['timestamp']==ref['timestamp']
    efrb=ROOT/'sifter_vis_d3/efrb-smoke.sqlite'
    eref=common.make_reference('efrb',efrb,OUT/'efrb-reference.json')
    rows=[]; erows=[]
    for rep in range(20):
        seed=20260928+rep
        for p,s in settings:
            label=f'p{p:g}-s{s}-r{rep:02d}'
            folder,db=convert(label,p,s,seed)
            result=common.evaluate('valkey',db,reference,seed,s,folder)
            payload=json.loads((folder/'representatives.json').read_text())
            row=dict(p=p,s=s,seed=seed,label=label,**rare.score(result,payload,ref))
            row['selection']=payload.get('selection',payload.get('selection_info'))
            assert not row['minimum_violations']
            assert row['displayed_pages']<=128
            row['prepared_records']=sum(len(v['events']) for v in payload['page_num_events'].values())
            assert row['prepared_records']<=100000
            rows.append(row);common.save(folder/'scored.json',row)
            (OUT/'progress.json').write_text(json.dumps(dict(status='running',completed=len(rows),total=100)))
            print(json.dumps(dict(trial=label,rare=row['display_success'],common=row['original_robj_success'])),flush=True)
            del payload,result;gc.collect()
        folder=OUT/f'efrb-r{rep:02d}';folder.mkdir()
        erows.append(common.evaluate('efrb',efrb,eref,seed,1,folder));gc.collect()
    common.save(OUT/'all-results.json',rows)
    common.save(OUT/'summary.json',dict(valkey=rare.summarize(rows),efrb=dict(trials=len(erows),
        display_success=sum(bool(r['displayed_qualifying_pages']) for r in erows))))
    (OUT/'progress.json').write_text(json.dumps(dict(status='completed',completed=100,total=100)))
if __name__=='__main__':main()
