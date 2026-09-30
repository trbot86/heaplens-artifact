"""Native conversion worker: disposable input copies and logical SQLite hashes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import sqlite3
import subprocess
import time

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--policy',choices=['prefix','direct'],required=True)
ap.add_argument('--output',required=True)
args=ap.parse_args()
work=Path('/tmp/native-input')
work.mkdir()
files=['binary_dump.txt','typeset_dump.txt','fileset_dump.txt','fielddump.txt']
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return h.hexdigest()
hashes={f:digest(Path('/logs')/f) for f in files}
for f in files:shutil.copy2(Path('/logs')/f,work/f)
environment=dict(os.environ,HEAPLENS_DIRECT_PREFIX='1' if args.policy=='direct' else '0')
command=['/evidence/native-convert','--sample','1','--num-pages-per-type','1',
         '--page-size','4096','--num-buckets','3000','--seed','20260929',
         '--field-dump','fielddump.txt']
started=time.perf_counter()
result=subprocess.run(command,cwd=work,env=environment,capture_output=True,text=True,timeout=280)
elapsed=time.perf_counter()-started
print(result.stdout,flush=True)
print(result.stderr,flush=True)
result.check_returncode()
assert all(digest(work/f)==hashes[f] for f in files),'Converter did not restore its disposable input'
db=work/'allocs.sqlite'
tables={}
with sqlite3.connect(db) as connection:
    for name,sql in connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"):
        columns=list(connection.execute(f'PRAGMA table_info("{name}")'))
        order=','.join(str(i+1) for i in range(len(columns)))
        h=hashlib.sha256()
        count=0
        for row in connection.execute(f'SELECT * FROM "{name}" ORDER BY {order}'):
            h.update(json.dumps(row,separators=(',',':')).encode()+b'\n')
            count+=1
        tables[name]=dict(rows=count,sha256=h.hexdigest(),schema=sql)
phases={}
for line in result.stderr.splitlines():
    if line.startswith('ABLATION_PHASE '):
        _,name,value=line.split()
        phases[name]=float(value)
out=dict(policy=args.policy,conversion_seconds=elapsed,phases=phases,
         peak_native_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
         database_bytes=db.stat().st_size,tables=tables,inputs=hashes,command=command,
         source_events=(work/'binary_dump.txt').stat().st_size//40,status='complete')
Path(args.output).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('tables','inputs')}),flush=True)
