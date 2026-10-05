#!/usr/bin/env python3
"""Verify and unpack the retained HNSW perf-c2c example without recording hardware events."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sqlite3

BUNDLE=Path(__file__).resolve().parent


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as source:
        while chunk:=source.read(1024*1024):h.update(chunk)
    return h.hexdigest()


def report_rows(text):
    """The retained Intel total-HITM stdio layout, not offset/Pareto rows."""
    start='Shared Data Cache Line Table'
    stop='Shared Cache Line Distribution Pareto'
    if start not in text or stop not in text:raise ValueError('Missing cache-line table boundaries')
    table=text.split(start,1)[1].split(stop,1)[0]
    if not all(word in table for word in ('LclHitm','RmtHitm','Loads','Stores')):
        raise ValueError('Unsupported perf report columns')
    rows={}
    for line in table.splitlines():
        tokens=line.split()
        if not tokens or not tokens[0].isdigit():continue
        if len(tokens)!=23 or not re.fullmatch(r'0x[0-9a-fA-F]+',tokens[1]) or not tokens[4].endswith('%'):
            raise ValueError('Unexpected cache-line row: '+line)
        address=int(tokens[1],16)
        if address%64 or address in rows:raise ValueError('Duplicate or unaligned cache line')
        hitm=float(tokens[4][:-1]);loads=int(tokens[9]);stores=int(tokens[10])
        if not 0<=hitm<=100 or min(loads,stores)<0:raise ValueError('Invalid perf values')
        rows[address]=(hitm,loads,stores)
    if not rows:raise ValueError('No cache-line rows')
    return rows


def verify(bundle=BUNDLE):
    manifest=json.loads((bundle/'manifest.json').read_text())
    for name,entry in manifest['files'].items():
        if (bundle/name).stat().st_size!=entry['bytes'] or digest(bundle/name)!=entry['sha256']:
            raise ValueError('Retained input changed: '+name)
    rows=report_rows((bundle/'perf_c2c_report_for_db.txt').read_text())
    for address,hitm,loads,stores in manifest['database']['perf_rows']:
        if address not in rows or not math.isclose(hitm,rows[address][0],abs_tol=1e-6) or (loads,stores)!=rows[address][1:]:
            raise ValueError('Report/database values differ')
    return manifest,rows


def prepare(out,bundle=BUNDLE):
    manifest,rows=verify(bundle)
    out.mkdir(parents=True,exist_ok=False)
    database=out/'hnsw-perf-c2c.sqlite'
    with gzip.open(bundle/'allocs.sqlite.gz','rb') as source,database.open('xb') as target:
        shutil.copyfileobj(source,target)
    expected=manifest['database']
    if database.stat().st_size!=expected['bytes'] or digest(database)!=expected['sha256']:
        raise ValueError('Unpacked database differs from retained database')
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as con:
        if con.execute('PRAGMA quick_check').fetchone()!=('ok',):raise ValueError('Database integrity failure')
        actual=con.execute('SELECT CLADDRESS,HITM,LOADS,STORES FROM PERF ORDER BY CLADDRESS').fetchall()
        if list(map(list,actual))!=expected['perf_rows']:raise ValueError('Unexpected PERF contents')
        pages={address//4096 for address in rows}
        present={page for page in pages if con.execute('SELECT 1 FROM SUPERTABLE WHERE ADDRESS >= ? AND ADDRESS < ? LIMIT 1',(page*4096,(page+1)*4096)).fetchone()}
        matched={address for address in rows if address//4096 in present}
        if matched!={row[0] for row in actual}:raise ValueError('PERF pages differ from represented report pages')
    for name in ('perf_c2c_report_for_db.txt','perf_c2c_record.log','benchmark.log'):
        shutil.copy2(bundle/name,out/name)
    summary=dict(status='passed',database_sha256=expected['sha256'],report_cache_lines=len(rows),
        database_cache_lines=len(actual),mandatory_4k_pages=len(present),
        unmatched_report_cache_lines=[hex(a) for a in rows if a not in matched],
        capture_loss=manifest['capture_loss'],scope=manifest['scope'])
    with (out/'summary.json').open('x') as target:json.dump(summary,target,indent=2);target.write('\n')
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['verify','prepare'],nargs='?',default='verify')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args(argv)
    if args.command=='prepare':
        if args.out is None:parser.error('prepare requires a new --out directory')
        result=prepare(args.out)
    else:
        manifest,rows=verify()
        result=dict(status='passed',report_cache_lines=len(rows),database_cache_lines=len(manifest['database']['perf_rows']),scope=manifest['scope'])
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
