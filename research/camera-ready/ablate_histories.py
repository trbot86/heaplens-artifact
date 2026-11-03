"""Fixed-page full versus bucket-reduced display histories, research only."""
import argparse
import copy
import hashlib
import json
import random
import resource
import sys
import time
from pathlib import Path


def hashed(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def prepare(args, module):
    import numpy as np
    np.random.seed(20260929)
    random.seed(20260929)
    phases, counts = {}, {}
    started = time.perf_counter()
    def timed(name, fn):
        print(json.dumps({'checkpoint':name,'policy':args.policy}),flush=True)
        begin = time.perf_counter()
        value = fn()
        phases[name] = time.perf_counter()-begin
        return value
    s = timed('database', lambda: module.Sampler(args.database,args.page_size,64,2000))
    types = s.types()
    lines = timed('statistics',s.get_all_lines_and_stats)
    reduce = s.get_last_object_per_bucket
    def histories(df):
        counts['all_prepared_objects'] = len(df)
        out = df.copy() if args.policy == 'full' else reduce(df)
        counts['all_display_histories'] = len(out)
        return out
    s.get_last_object_per_bucket = histories
    original_selector = module.select_pages
    plan = json.loads(Path(args.plan).read_text()) if args.plan else None
    if plan:
        def fixed_selector(clusters, page_types, *a, **kwargs):
            chosen = set(plan['page_ids'])
            assert chosen <= set(page_types)
            info = copy.deepcopy(plan['selection'])
            info['selected_records'] = sum(kwargs['page_records'][p] for p in chosen)
            # Fixed experimental pages, not a promise to enforce the GUI's
            # record budget after changing the display-history representation.
            info['record_budget'] = None
            return chosen, info
        module.select_pages = fixed_selector
    try:
        pages = timed('pages',lambda:s.get_sample_of_pages(-1,-1,{t:True for t in types},
                          'mbkmeans',5,3,page_budget=128,record_budget=100000))
    finally:
        module.select_pages = original_selector
    layout = dict(features=pages['features'],clusters=pages['clusters'],
                  page_clusters={a:p['cluster'] for a,p in pages['page_num_events'].items()})
    layout_hash = hashed(layout)
    if plan:
        assert layout_hash == plan['layout_sha256'], 'Fixed fingerprints/clusters changed'
    if args.make_plan:
        Path(args.make_plan).write_text(json.dumps(dict(
            page_ids=sorted(int(a)//args.page_size for a in pages['page_num_events']),
            selection=pages['selection'],layout_sha256=layout_hash),indent=2)+'\n')
    cache = timed('cache',lambda:s.get_cache_data(32768,8))
    payload = timed('json',lambda:json.dumps(dict(types=types,linesAndStats=lines,pagesData=pages,
                               cacheData=cache),sort_keys=True,separators=(',',':')))
    result = dict(policy=args.policy,phases=phases,total_seconds=time.perf_counter()-started,
                  database_event_rows=len(s.all_data),**counts,
                  selected_pages=len(pages['page_num_events']),
                  selected_records=sum(len(p['events']) for p in pages['page_num_events'].values()),
                  payload_bytes=len(payload.encode()),
                  payload_sha256=None if getattr(args,'skip_output_hashes',False) else hashlib.sha256(payload.encode()).hexdigest(),
                  layout_sha256=layout_hash,
                  cache_sha256=None if getattr(args,'skip_output_hashes',False) else hashed(cache),
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,status='complete')
    return result,payload


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',required=True)
    ap.add_argument('--database',required=True)
    ap.add_argument('--page-size',type=int,required=True)
    ap.add_argument('--policy',choices=['reduced','full'],required=True)
    ap.add_argument('--plan')
    ap.add_argument('--make-plan')
    ap.add_argument('--output',required=True)
    ap.add_argument('--payload')
    args = ap.parse_args()
    sys.path.insert(0,str(Path(args.root)/'sifter_vis_d3/server'))
    import sampler
    result,payload = prepare(args,sampler)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    if args.payload:
        with Path(args.payload).open('x') as f:
            f.write(payload)
    print(json.dumps(result),flush=True)
