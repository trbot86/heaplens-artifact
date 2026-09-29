"""Frozen-input baseline/cluster-first comparison; outputs are author evidence."""
import argparse
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import time
import numpy as np
import simplejson
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sifter_vis_d3/server'))
import sampler as candidate

def sha(path):
    digest=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(2**20),b''): digest.update(chunk)
    return digest.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('database')
    ap.add_argument('--page-size',type=int,default=4096)
    ap.add_argument('--out',required=True)
    ap.add_argument('--baseline-root',default='/baseline')
    ap.add_argument('--rax-reference',required=True)
    ap.add_argument('--prior-results',required=True)
    a=ap.parse_args()
    out=Path(a.out)/a.name
    out.mkdir(parents=True)
    baseline_file=Path(a.baseline_root)/'sifter_vis_d3/server/sampler.py'
    spec=importlib.util.spec_from_file_location('baseline_sampler',baseline_file)
    baseline=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    prior=json.loads(Path(a.prior_results).read_text())
    priors={r['seed']:r for r in prior['trials'] if r['budget']==prior['default_budget']}
    assert sha(a.database)==prior['database_sha256']
    assert sha(baseline_file)==prior['backend_sha256']
    ref=json.loads(Path(a.rax_reference).read_text())
    genuine={(e['addr'],e['allocTs'],e['size']) for e in ref['crossing_objects']}
    # Preserve reusable page histories: production conversion mutates freeTs.
    for module in (baseline,candidate):
        original=module.replace_nan
        module.replace_nan=lambda event,key,fn=original:fn(event.copy(),key)
    rows=[]
    with (out/'backend.log').open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        np.random.seed(20260928)
        s=baseline.Sampler(a.database,a.page_size,64,2000)
        mask={t:True for t in s.types()}
        labeled,features,perf=s.get_clusters_of_pages(-1,-1,mask,'mbkmeans')
        matrix=StandardScaler().fit_transform(features.drop(columns=['cluster']))
        requested=min(2*len(s.types()),len(features))
        default=prior['default_budget']
        available={e[baseline.TYPE_IND] for history in labeled[0] for e in history}
        for seed in range(20260928,20260948):
            np.random.seed(seed)
            labels=MiniBatchKMeans(n_clusters=requested).fit_predict(matrix)
            assert np.array_equal(features.index,labeled.index)
            labeled.loc[:,'cluster']=labels
            features.loc[:,'cluster']=labels
            for policy in ('baseline','cluster-first'):
                obj=s if policy=='baseline' else candidate.Sampler.__new__(candidate.Sampler)
                obj.page_size=a.page_size
                obj.get_clusters_of_pages=lambda *args,**kwargs:(labeled,features,perf)
                for budget in (default,64,128):
                    random.seed(seed)
                    before=time.perf_counter()
                    if policy=='baseline':
                        baseline.MAX_PAGE_PROP=(budget+.25)*np.log2(a.page_size)**2
                        result=obj.get_sample_of_pages(-1,-1,mask,'mbkmeans',5,3)
                    else:
                        result=obj.get_sample_of_pages(-1,-1,mask,'mbkmeans',5,3,page_budget=budget)
                    elapsed=time.perf_counter()-before
                    selected_types={e['type'] for page in result['page_num_events'].values() for e in page['events']}
                    row=dict(seed=seed,policy=policy,budget=budget,
                        available_clusters=int(result['num_clusters']),represented_clusters=len(result['clusters']),
                        selected_pages=len(result['page_num_events']),available_types=len(available),
                        represented_types=len(selected_types & available),omitted_types=sorted(available-selected_types),
                        selection_seconds=elapsed,selection=result.get('selection'))
                    if policy=='baseline' and budget==default:
                        expected=priors[seed]
                        assert row['selected_pages']==expected['selected_pages']
                        assert row['represented_clusters']==expected['represented_clusters']
                        assert row['available_clusters']==expected['clusters']
                    if policy=='cluster-first':
                        forced=row['selection']['mandatory_perf_pages']
                        assert row['selected_pages']<=max(budget,forced)
                        assert row['omitted_types']==row['selection']['omitted_types']
                        if row['available_clusters']<=budget and not forced:
                            assert row['represented_clusters']==row['available_clusters']
                    if a.name=='valkey-full':
                        hits={(e['addr'],e['allocTs'],e['size']) for page in result['page_num_events'].values()
                              for e in page['events'] if e['type']=='raxNode' and e['actualAddr']==e['addr']
                              and e['allocTs']<=ref['timestamp']
                              and (e['freeTs'] is None or e['freeTs']>ref['timestamp'])} & genuine
                        row.update(rax_success=bool(hits),rax_genuine_objects=len(hits))
                        if policy=='baseline' and budget==default:
                            assert row['rax_genuine_objects']==priors[seed]['rax_genuine_objects']
                    rows.append(row)
                    if seed==20260928 and policy=='cluster-first':
                        (out/f'pages-{budget}.json').write_text(simplejson.dumps(result,ignore_nan=True))
            print(json.dumps(dict(case=a.name,seed=seed,progress=len(rows))),file=sys.__stdout__,flush=True)
    result=dict(name=a.name,database_sha256=sha(a.database),page_size=a.page_size,
                baseline_sha256=sha(baseline_file),candidate_sha256=sha(ROOT/'sifter_vis_d3/server/sampler.py'),
                selector_sha256=sha(ROOT/'sifter_vis_d3/server/page_selection.py'),
                all_baseline_default_trials_replayed=True,trials=rows)
    (out/'results.json').write_text(json.dumps(result,indent=2))

if __name__=='__main__': main()
