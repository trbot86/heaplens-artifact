"""Bounded, local schema comparison on copies of retained databases.

No original extents are inferred from incomplete historical samples. Unknown
sizes are zero in BOTH comparison schemas, isolating the cost of the joins.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sqlite3
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sifter_vis_d3/server'))

def worker(path, phase):
    from sampler import Sampler
    start = time.perf_counter()
    if phase == 'query':
        digest = hashlib.sha256()
        with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
            rows = db.execute('SELECT * FROM SUPERTABLE').fetchall()
        elapsed = time.perf_counter()-start
        for row in rows:
            digest.update(repr(row).encode())
        result = dict(rows=len(rows), sha256=digest.hexdigest())
    else:
        s = Sampler(str(path))
        if phase == 'lifetimes':
            frame = s.get_objects(s.all_data)
        else:
            frame = s.all_data
        elapsed = time.perf_counter()-start
        import pandas as pd
        result = dict(rows=len(frame), sha256=hashlib.sha256(
            pd.util.hash_pandas_object(frame, index=True).values.tobytes()).hexdigest())
    result.update(seconds=elapsed, maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    print(json.dumps(result))

def prepare(src, out):
    baseline=out/'text.sqlite'; normalized=out/'lookups.sqlite'
    with sqlite3.connect(f'file:{src}?mode=ro',uri=True) as source, sqlite3.connect(baseline) as db:
        source.backup(db)
        cols={r[1] for r in db.execute('PRAGMA table_info(SUPERTABLE)')}
        if 'ACTUALSIZE' not in cols:
            db.execute('ALTER TABLE SUPERTABLE ADD COLUMN ACTUALSIZE INT NOT NULL DEFAULT 0')
        db.commit(); db.execute('VACUUM')
    with sqlite3.connect(baseline) as source, sqlite3.connect(normalized) as db:
        source.backup(db)
        db.executescript('''
          ALTER TABLE SUPERTABLE RENAME TO OLD_EVENTS;
          CREATE TABLE FILE_NAMES(ID INTEGER PRIMARY KEY, NAME TEXT);
          CREATE TABLE TYPE_NAMES(ID INTEGER PRIMARY KEY, NAME TEXT);
          INSERT INTO FILE_NAMES(NAME) SELECT DISTINCT FILE FROM OLD_EVENTS;
          INSERT INTO TYPE_NAMES(NAME) SELECT DISTINCT TYPE FROM OLD_EVENTS;
          CREATE TABLE EVENTS(FILE_ID INT, LINE INT, TIMESTAMP INT, SIZE INT,
            ACTUALADDR INT, ADDRESS INT, isNew INT, TYPE_ID INT, ACTUALSIZE INT);
          INSERT INTO EVENTS SELECT F.ID,E.LINE,E.TIMESTAMP,E.SIZE,E.ACTUALADDR,E.ADDRESS,E.isNew,T.ID,E.ACTUALSIZE
            FROM OLD_EVENTS E JOIN FILE_NAMES F ON E.FILE IS F.NAME JOIN TYPE_NAMES T ON E.TYPE IS T.NAME;
          DROP TABLE OLD_EVENTS;
          CREATE VIEW SUPERTABLE AS SELECT F.NAME AS FILE,E.LINE,E.TIMESTAMP,E.SIZE,E.ACTUALADDR,E.ADDRESS,E.isNew,
            T.NAME AS TYPE,E.ACTUALSIZE FROM EVENTS E JOIN FILE_NAMES F ON F.ID=E.FILE_ID JOIN TYPE_NAMES T ON T.ID=E.TYPE_ID;
        ''')
        db.execute('VACUUM')
    return dict(text=baseline,lookups=normalized)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path); ap.add_argument('--out',type=Path)
    ap.add_argument('--worker',type=Path); ap.add_argument('--phase')
    ap.add_argument('--prepared', type=Path)
    args=ap.parse_args()
    if args.worker: return worker(args.worker,args.phase)
    args.out.mkdir(parents=True,exist_ok=False)
    paths=(dict(text=args.prepared/'text.sqlite',lookups=args.prepared/'lookups.sqlite')
           if args.prepared else prepare(args.input,args.out))
    results=dict(input=str(args.input),bytes={k:p.stat().st_size for k,p in paths.items()},
                 protocol='One discarded warmup, then five alternating trials per schema and phase; OS caches not flushed.',trials=[])
    for phase in ('query','load','lifetimes'):
        expected=None
        for trial in range(6):
            for name in (('text','lookups') if trial%2==0 else ('lookups','text')):
                output=subprocess.check_output([sys.executable,__file__,'--worker',str(paths[name]),'--phase',phase],text=True,timeout=180)
                row=json.loads(output.strip().splitlines()[-1])
                if expected is None: expected=(row['rows'],row['sha256'])
                assert expected==(row['rows'],row['sha256']), (phase,name,'different output')
                row.update(phase=phase,schema=name,trial=trial,warmup=trial==0)
                results['trials'].append(row)
                (args.out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        for name in paths:
            rows=[r for r in results['trials'] if r['phase']==phase and r['schema']==name and not r['warmup']]
            print(phase,name,statistics.median(r['seconds'] for r in rows),flush=True)
    print(json.dumps(results['bytes']),flush=True)

if __name__=='__main__': main()
