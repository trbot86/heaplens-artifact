"""Interleaved fresh-Sampler full-preparation comparisons on retained inputs."""
import argparse, contextlib, hashlib, importlib.util, json, random, sys, time
from pathlib import Path
import numpy as np

ap=argparse.ArgumentParser();ap.add_argument('name');ap.add_argument('database')
ap.add_argument('--page-size',type=int,default=4096);ap.add_argument('--out',required=True)
a=ap.parse_args();out=Path(a.out)/a.name;out.mkdir(parents=True)
sys.path.insert(0,'/candidate/sifter_vis_d3/server')
def module(root,name):
    spec=importlib.util.spec_from_file_location(name,root+'/sifter_vis_d3/server/sampler.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
modules={'baseline':module('/baseline','old_sampler'),'optimized':module('/candidate','new_sampler')}
rows=[];expected=None
with (out/'backend.log').open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
    for rep in range(3):
        for policy in (('baseline','optimized') if rep%2==0 else ('optimized','baseline')):
            np.random.seed(20260928);random.seed(20260928);phases={};start=time.perf_counter()
            def timed(name,fn):
                tick=time.perf_counter();value=fn();phases[name]=time.perf_counter()-tick;return value
            s=timed('database',lambda:modules[policy].Sampler(a.database,a.page_size,64,2000))
            types=s.types();lines=timed('statistics',s.get_all_lines_and_stats)
            pages=timed('pages',lambda:s.get_sample_of_pages(-1,-1,{t:True for t in types},'mbkmeans',5,3))
            cache=timed('cache',lambda:s.get_cache_data(32768,8))
            payload=timed('json',lambda:json.dumps(dict(types=types,linesAndStats=lines,pagesData=pages,cacheData=cache),separators=(',',':')))
            elapsed=time.perf_counter()-start;digest=hashlib.sha256(payload.encode()).hexdigest()
            if expected is None:expected=digest
            assert digest==expected,'Complete initial payload changed'
            row=dict(rep=rep,policy=policy,total_seconds=elapsed,phases=phases,payload_sha256=digest,payload_bytes=len(payload))
            rows.append(row);print(json.dumps(row),file=sys.__stdout__,flush=True)
            del s,lines,pages,cache,payload
(out/'backend.json').write_text(json.dumps(dict(case=a.name,complete_payload_equal=True,rows=rows),indent=2))
