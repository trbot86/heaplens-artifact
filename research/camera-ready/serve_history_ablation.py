"""Actual database preparation per HTTP request; no prepared-payload replay."""
import argparse
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from flask import Flask, Response, abort, request
from flask_cors import CORS
from ablate_histories import prepare

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--root',default='/candidate')
args=ap.parse_args()
sys.path.insert(0,str(Path(args.root)/'sifter_vis_d3/server'))
import sampler
app=Flask(__name__)
CORS(app)
sequence=0
palettes={}
for case in ('valkey','bcco'):
    saved=json.loads(Path(f'/evidence/history-{case}-reduced-payload.json').read_text())
    names=dict.fromkeys(saved['types']+saved['cacheData']['idxToTpAndSt'])
    palettes[case]=[dict(type=tp,colour=f'hsl({i*137%360},40%,45%)') for i,tp in enumerate(names)]
    del saved

@app.get('/init-app/<path:config>')
def init(config):
    global sequence
    label=config.split('.sqlite')[0]
    parts=label.rsplit('--',1)
    if len(parts)!=2 or parts[1] not in ('full','reduced'):abort(404)
    name={'valkey':'valkey','tpcc-bcco-2m':'bcco'}.get(parts[0])
    if not name:abort(404)
    begin=time.perf_counter()
    options=SimpleNamespace(database=f'/inputs/{name}.sqlite',page_size=4096 if name=='valkey' else 2097152,
              policy=parts[1],plan=f'/evidence/history-{name}-plan.json',make_plan=None,skip_output_hashes=True)
    row,payload=prepare(options,sampler)
    row.update(case=name,sequence=sequence,http_prepare_seconds=time.perf_counter()-begin)
    sequence+=1
    with Path('/evidence/history-http.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    response=Response(payload,mimetype='application/json')
    response.headers['Server-Timing']=f'prepare;dur={row["total_seconds"]*1000:.3f}'
    response.headers['Cache-Control']='no-store'
    return response

@app.get('/log-data/get-colours/<path:config>')
def colours(config):
    return palettes['valkey' if config.startswith('valkey') else 'bcco']

@app.get('/log-data/get-notes/<path:config>')
def notes(config):
    return '""',{'Content-Type':'application/json'}

@app.get('/health')
def health():return {'ready':True}

app.run(host='0.0.0.0',port=5000,threaded=False)
