"""Same prepared histories/clusters, page-only vs cost-aware representative selection.

Author evidence, not a change to artifact/run.sh. Inputs are existing retained
traces; --reference is the previously audited genuine raxNode identity oracle.
"""
import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import numpy as np
import simplejson
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sifter_vis_d3/server'))
import sampler
from page_selection import select_pages


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name'); ap.add_argument('database'); ap.add_argument('--page-size', type=int, default=4096)
    ap.add_argument('--out', required=True); ap.add_argument('--reference', required=True)
    args = ap.parse_args()
    out = Path(args.out)/args.name; out.mkdir(parents=True, exist_ok=True)
    oracle = json.loads(Path(args.reference).read_text())
    genuine = {(e['addr'], e['allocTs'], e['size']) for e in oracle['crossing_objects']}
    original = sampler.replace_nan
    sampler.replace_nan = lambda event, key: original(event.copy(), key)
    rows = []
    with (out/'prepare.log').open('w') as log, contextlib.redirect_stdout(log):
        np.random.seed(20260928)
        s = sampler.Sampler(args.database, args.page_size, 64, 2000)
        mask = {tp: True for tp in s.types()}
        labeled, features, perf = s.get_clusters_of_pages(-1, -1, mask, 'mbkmeans')
        matrix = StandardScaler().fit_transform(features.drop(columns=['cluster']))
        types = {p: {e[sampler.TYPE_IND] for e in events if isinstance(e[sampler.TYPE_IND], str)}
                 for p, events in labeled[0].items()}
        costs = {p: len(events) for p, events in labeled[0].items()}
        forced = set(perf.loc[perf['page_num'].isin(labeled.index), 'page_num'])
        for seed in range(20260928, 20260948):
            np.random.seed(seed)
            labels = MiniBatchKMeans(n_clusters=min(2*len(s.types()), len(features))).fit_predict(matrix)
            labeled.loc[:, 'cluster'] = labels; features.loc[:, 'cluster'] = labels
            clusters = labeled.groupby('cluster', sort=False).groups
            for cap in (None, 25000, 50000, 100000):
                start = time.perf_counter()
                pages, info = select_pages(clusters, types, 128, 5, 3, forced_pages=forced,
                    page_records=costs, record_budget=cap, rng=random.Random(seed))
                row = dict(seed=seed, cap=cap, seconds=time.perf_counter()-start, **info)
                if args.name == 'valkey-full':
                    hits = {(e[2], e[4], e[1]) for p in pages for e in labeled.loc[p, 0]
                            if e[3] == 'raxNode' and e[7] == e[2] and e[4] <= oracle['timestamp']
                            and (not np.isfinite(e[5]) or e[5] > oracle['timestamp'])} & genuine
                    row['rax_genuine_objects'] = len(hits)
                assert info['selected_records'] <= max(cap or float('inf'), info['mandatory_perf_records'])
                rows.append(row)
                if seed == 20260928 and cap == 100000:
                    s.get_clusters_of_pages = lambda *a, **kw: (labeled, features, perf)
                    random.seed(seed)
                    payload = s.get_sample_of_pages(-1, -1, mask, 'mbkmeans', 5, 3,
                                                   page_budget=128, record_budget=cap)
                    (out/'pages.json').write_text(simplejson.dumps(payload, ignore_nan=True))
            print(f'{args.name}: seed {seed} complete', file=sys.__stdout__, flush=True)
    result = dict(name=args.name, page_size=args.page_size, eligible_pages=len(costs),
        total_prepared_records=sum(costs.values()), max_page_records=max(costs.values(), default=0),
        database_sha256=sha256(args.database),
        selector_sha256=hashlib.sha256((ROOT/'sifter_vis_d3/server/page_selection.py').read_bytes()).hexdigest(),
        trials=rows)
    (out/'results.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__': main()
