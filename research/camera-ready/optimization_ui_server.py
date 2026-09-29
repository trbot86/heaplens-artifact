"""Replay identical cluster-first payloads for baseline/optimized UI comparisons."""
from pathlib import Path
import json
from flask import Flask, Response
from flask_cors import CORS
app=Flask(__name__);CORS(app)
root=Path('/author-tools')
palettes={}
for case in ('valkey-full','tpcc-bcco-2m'):
    common=json.loads((root/'budget-latency-20260928'/case/'common.json').read_text())
    names=list(dict.fromkeys(common['types']+common['cacheData']['idxToTpAndSt']))
    palettes[case]=[dict(type=tp,colour=f'hsl({i*137%360}, 40%, 45%)') for i,tp in enumerate(names)]
    del common
@app.after_request
def headers(r):r.headers['Cache-Control']='no-store';return r
@app.get('/get-fnames')
def files():return ['valkey-full--52.sqlite','tpcc-bcco-2m--17.sqlite','tpcc-bcco-2m--128.sqlite']
@app.get('/init-app/<path:config>')
def init(config):
    case,budget=config.split('.sqlite-')[0].split('--')
    assert (case,budget) in [('valkey-full','52'),('tpcc-bcco-2m','17'),('tpcc-bcco-2m','128')]
    common=(root/'budget-latency-20260928'/case/'common.json').read_bytes()
    pages=(root/'cluster-first-20260928'/case/f'pages-{budget}.json').read_bytes()
    return Response(common[:-1]+b',"pagesData":'+pages+b'}',mimetype='application/json')
@app.get('/log-data/get-colours/<path:name>')
def colours(name):return palettes[name.split('--')[0]]
@app.get('/log-data/get-notes/<path:name>')
def notes(name):return Response('""',mimetype='application/json')
@app.get('/log-data/get-files')
def logfiles():return []
app.run(host='0.0.0.0',port=5000,threaded=False)
