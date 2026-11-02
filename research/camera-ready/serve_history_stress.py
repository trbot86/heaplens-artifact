"""HTTP transport cross-check for the synthetic huge-page browser stress."""
import json
import os
from pathlib import Path
from flask import Flask, Response
from flask_cors import CORS

root = Path('/author-tools')
common = json.loads((root/'budget-latency-20260928/tpcc-bcco-2m/common.json').read_text())
pages = json.loads((root/'history-budget-20260928/tpcc-bcco-2m/pages.json').read_text())
total = int(os.environ.get('HEAPLENS_STRESS_RECORDS', '250000'))
addresses = list(pages['page_num_events'])
left = total
for i, addr in enumerate(addresses):
    count = (left + len(addresses)-i-1)//(len(addresses)-i); left -= count
    page = pages['page_num_events'][addr]
    tp = next((e['type'] for e in page['events'] if e['type']), common['types'][0])
    page['events'] = [dict(file=None, line=0, addr=int(addr)+j*32 % 2097152,
        actualAddr=int(addr)+j*32 % 2097152, size=32, type=tp,
        allocTs=common['linesAndStats']['minTs'], freeTs=None) for j in range(count)]
pages['selection']['selected_records'] = total
payload = json.dumps(dict(**common, pagesData=pages)).encode()
types = list(dict.fromkeys(common['types']+common['cacheData']['idxToTpAndSt']))
palette = [dict(type=tp, colour=f'hsl({i*137%360},40%,45%)') for i, tp in enumerate(types)]
print(f'HTTP stress payload: {len(payload)} bytes, {total} records', flush=True)
del common, pages
app = Flask(__name__); CORS(app)


@app.get('/init-app/<path:config>')
def init(config):
    return Response(payload, mimetype='application/json')


@app.get('/log-data/get-colours/<path:name>')
def colours(name): return palette


@app.get('/log-data/get-notes/<path:name>')
def notes(name): return Response('""', mimetype='application/json')


app.run(host='0.0.0.0', port=5000)
