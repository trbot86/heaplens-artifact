"""Read-only backend profile. No alternative implementation is installed."""
import argparse
import cProfile
import contextlib
import json
from pathlib import Path
import pstats
import random
import sys
import time
import numpy as np

ap=argparse.ArgumentParser()
ap.add_argument('name')
ap.add_argument('database')
ap.add_argument('--page-size',type=int,default=4096)
ap.add_argument('--baseline-root',default='/baseline')
ap.add_argument('--out',required=True)
a=ap.parse_args()
sys.path.insert(0,str(Path(a.baseline_root)/'sifter_vis_d3/server'))
from sampler import Sampler
out=Path(a.out)/a.name
out.mkdir(parents=True)
profile=cProfile.Profile()
timings={}
def timed(name,fn):
    start=time.perf_counter();value=fn();timings[name]=time.perf_counter()-start;return value
with (out/'backend.log').open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
    np.random.seed(20260928);random.seed(20260928)
    profile.enable()
    s=timed('database',lambda:Sampler(a.database,a.page_size,64,2000))
    types=s.types()
    lines=timed('statistics',s.get_all_lines_and_stats)
    pages=timed('pages',lambda:s.get_sample_of_pages(-1,-1,{t:True for t in types},'mbkmeans',5,3))
    cache=timed('cache',lambda:s.get_cache_data(32768,8))
    encoded=timed('json',lambda:json.dumps(dict(types=types,linesAndStats=lines,pagesData=pages,cacheData=cache)))
    profile.disable()
profile.dump_stats(str(out/'preparation.prof'))
with (out/'profile.txt').open('w') as f:
    stats=pstats.Stats(profile,stream=f)
    stats.sort_stats('cumulative').print_stats(45)
    stats.sort_stats('tottime').print_stats(25)
(out/'timings.json').write_text(json.dumps(dict(profiled_seconds=timings,response_bytes=len(encoded.encode())),indent=2))
print(json.dumps(dict(case=a.name,timings=timings)),flush=True)
