"""Offline cache-update prototype. Original get_cache_data except two updates."""
import argparse
import ast
import contextlib
import inspect
import json
from pathlib import Path
import random
import sys
import textwrap
import time
import numpy as np

ap=argparse.ArgumentParser()
ap.add_argument('name');ap.add_argument('database');ap.add_argument('--page-size',type=int,default=4096)
ap.add_argument('--out',required=True)
a=ap.parse_args()
sys.path.insert(0,'/baseline/sifter_vis_d3/server')
import sampler

def add_cache_range(data, bucket, start_set, type_idx, count, num_sets, delta):
    if count<0: raise ValueError('negative cache-line count')
    if count==1:
        data[bucket,start_set,type_idx]+=delta
        return
    cycles,remainder=divmod(count,num_sets)
    if cycles: data[bucket,:,type_idx]+=cycles*delta
    first=min(remainder,num_sets-start_set)
    if first: data[bucket,start_set:start_set+first,type_idx]+=delta
    if remainder>first: data[bucket,:remainder-first,type_idx]+=delta

class ReplaceUpdates(ast.NodeTransformer):
    def __init__(self): self.count=0
    def visit_Expr(self,node):
        call=node.value
        if isinstance(call,ast.Call) and ast.unparse(call.func)=='np.add.at':
            self.count+=1
            # The original index tuple has np.full(n_sets, time_bucket) first.
            bucket=call.args[1].elts[0].args[1]
            return ast.copy_location(ast.Expr(value=ast.Call(func=ast.Name(id='add_cache_range',ctx=ast.Load()),
                args=[ast.Name(id='data',ctx=ast.Load()),bucket,
                      ast.Name(id='start_set',ctx=ast.Load()),
                      ast.parse('tp_and_st_to_idx[entry[TYPE_IND]]',mode='eval').body,
                      ast.Name(id='n_sets',ctx=ast.Load()),ast.Name(id='num_cache_sets',ctx=ast.Load()),call.args[2]],
                keywords=[])),node)
        # This allocated vector is not used after the two replacements.
        return self.generic_visit(node)
    def visit_Assign(self,node):
        if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='cache_sets':
            return None
        return self.generic_visit(node)

tree=ast.parse(textwrap.dedent(inspect.getsource(sampler.Sampler.get_cache_data)))
transform=ReplaceUpdates();tree=transform.visit(tree);ast.fix_missing_locations(tree)
assert transform.count==2
namespace={**vars(sampler),'add_cache_range':add_cache_range}
exec(compile(tree,'<offline-cache-update-prototype>','exec'),namespace)
class Prototype(sampler.Sampler): get_cache_data=namespace['get_cache_data']

# Repeated cache-set indices and wraparound must retain their multiplicities.
for sets in (1,2,7,64):
    for start in range(sets):
        for count in (0,1,sets-1,sets,sets+1,sets*3+5):
            for delta in (-1,1):
                slow=np.zeros((2,sets,2));fast=slow.copy()
                np.add.at(slow,(np.full(count,1),(start+np.arange(count))%sets,np.full(count,1)),delta)
                add_cache_range(fast,1,start,1,count,sets,delta)
                assert np.array_equal(slow,fast)
out=Path(a.out)/a.name
out.mkdir(exist_ok=True,parents=True)
rows=[]
reference=None
with (out/'cache-update.log').open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
    for cls,policy in ((sampler.Sampler,'baseline'),(Prototype,'range-updates')):
        random.seed(20260928);np.random.seed(20260928)
        s=cls(a.database,a.page_size,64,2000)
        start=time.perf_counter();result=s.get_cache_data(32768,8);elapsed=time.perf_counter()-start
        if reference is None: reference=result
        else: assert result==reference,'Full cache output differs'
        rows.append(dict(policy=policy,seconds=elapsed,buckets=len(result['occ']),columns=len(result['occ'][0])))
        del s
(out/'cache-update.json').write_text(json.dumps(dict(name=a.name,full_output_equal=True,
    methodology='One unprofiled invocation per implementation; identical fresh sampler inputs. Only cache-line delta accumulation changed; no integrated optimization.',rows=rows),indent=2))
print(json.dumps(dict(case=a.name,full_output_equal=True,rows=rows)),flush=True)
