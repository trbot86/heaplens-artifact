"""Prepared, synthetic HTTP fixtures: UI cost only, not database preprocessing.

The retained cache/statistics panels are fixed controls, not summaries of these
synthetic objects. Selection limits are deliberately bypassed. No production
source is changed. Run with --prepare before starting the browser measurements.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

CASES = [("live100k", 100000, 128, False),
         ("live250k", 250000, 128, False),
         ("live1m", 1000000, 128, False),
         ("churn1m", 1000000, 128, True),
         ("dense1m", 1048576, 16, False),
         ("dense64k", 65536, 1, False)]


def prepare(source, output, only=None):
    common = json.loads((source / 'budget-latency-20260928/tpcc-bcco-2m/common.json').read_text())
    original = json.loads((source / 'history-budget-20260928/tpcc-bcco-2m/pages.json').read_text())
    lo, hi = common['linesAndStats']['minTs'], common['linesAndStats']['maxTs']
    output.mkdir(parents=True, exist_ok=True)
    palette = [dict(type=tp, colour=f'hsl({i*137%360},40%,45%)') for i, tp in
               enumerate(dict.fromkeys(common['types'] + common['cacheData']['idxToTpAndSt']))]
    (output / 'palette.json').write_text(json.dumps(palette))
    manifest = []
    for name, count, n_pages, churn in CASES:
        if only and name != only: continue
        pages = copy.deepcopy(original)
        addresses = list(pages['page_num_events'])[:n_pages]
        pages['page_num_events'] = {a: pages['page_num_events'][a] for a in addresses}
        left = count
        for i, address in enumerate(addresses):
            n = (left + n_pages-i-1)//(n_pages-i)
            left -= n
            events = []
            slots = (n+9)//10 if churn else n
            assert slots*32 <= 2097152
            for j in range(n):
                # Churn has ten nonoverlapping lifetimes per address, with
                # 80% duty cycle. Live cases have unique object addresses.
                cohort = j//slots if churn else 0
                addr = int(address)+(j % slots)*32
                events.append(dict(file=None, line=0, addr=addr, actualAddr=addr,
                    size=32, type='char',
                    allocTs=lo+int((hi-lo)*cohort/10) if churn else lo,
                    freeTs=lo+int((hi-lo)*(cohort+.8)/10) if churn else None))
            pages['page_num_events'][address]['events'] = events
        represented = {str(p['cluster']) for p in pages['page_num_events'].values()}
        pages['clusters'] = {c: v for c, v in pages['clusters'].items() if c in represented}
        pages['num_clusters'] = len(represented)
        pages['sum_cluster_sizes'] = sum(c['size'] for c in pages['clusters'].values())
        pages['selection'].update(selected_records=count, selected_pages=n_pages,
            page_budget=n_pages, record_budget=count, omitted_clusters=[],
            omitted_types=[], represented_clusters=len(represented),
            available_clusters=len(represented))
        destination = output / (name+'.json')
        with destination.open('w') as f:
            json.dump(dict(**common, pagesData=pages), f, separators=(',', ':'))
        digest = hashlib.sha256()
        with destination.open('rb') as f:
            while chunk := f.read(1024*1024): digest.update(chunk)
        row = dict(name=name, records=count, pages=n_pages, churn=churn,
            max_records_per_page=max(len(p['events']) for p in pages['page_num_events'].values()),
            bytes=destination.stat().st_size, sha256=digest.hexdigest())
        manifest.append(row)
        print(json.dumps(row), flush=True)
    (output/('manifest-'+only+'.json' if only else 'manifest.json')).write_text(json.dumps(manifest, indent=2))


def serve(output):
    from flask import Flask, abort, send_file
    from flask_cors import CORS
    app = Flask(__name__)
    CORS(app)

    @app.get('/init-app/<path:config>')
    def init(config):
        name = config.split('--')[-1].split('.sqlite')[0]
        if name not in {c[0] for c in CASES}: abort(404)
        return send_file(output/(name+'.json'), mimetype='application/json', max_age=0)

    @app.get('/log-data/get-colours/<path:name>')
    def colours(name): return send_file(output/'palette.json', mimetype='application/json', max_age=0)

    @app.get('/log-data/get-notes/<path:name>')
    def notes(name): return '""', {'Content-Type': 'application/json'}

    app.run(host='0.0.0.0', port=5000, threaded=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--only', choices=[c[0] for c in CASES])
    parser.add_argument('--source', type=Path, default=Path('/author-tools'))
    parser.add_argument('--output', type=Path, default=Path('/fixtures'))
    args = parser.parse_args()
    if args.prepare: prepare(args.source, args.output, args.only)
    else: serve(args.output)
