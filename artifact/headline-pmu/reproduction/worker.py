"""Container entry point. The host controller owns locking, bounds and storage."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/'drivers'),'/root/sifter/artifact']
from trace_store import TraceStore, write_json, sha
from portable_runtime import expected_traces


def invoke(module, args=()):
    subprocess.run([sys.executable,'-B',str(HERE/'drivers'/module),*args],check=True)


def build(family, apps):
    if family=='ascylib':
        import prepare_ascylib as prep
        prep.SPECS={k:v for k,v in prep.SPECS.items() if 'ascylib_'+k in apps}
        prep.main()
    elif family=='tpcc':
        import prepare_tpcc as prep
        prep.SPECS={k:v for k,v in prep.SPECS.items() if 'tpcc_'+k in apps}
        prep.main()
    elif family=='rocks':
        # Same C++ logger as the historical TPC-C preparation; build it even
        # when only RocksDB was selected. No TPC-C workload/build is required.
        import prepare_tpcc as prep
        prep.SPECS={}
        prep.main()
        for app in ('hsl','isl'):
            if 'rocks_'+app in apps:
                for variant in ('before','after'):
                    invoke('prepare_rocks.py',['--app',app,'--variant',variant])
    elif family=='hnsw':
        invoke('prepare_hnsw.py')
    elif family=='valkey':
        from prepare_valkey import prepare
        for variant in ('baseline','optimized'):
            for logging in (False,True):
                prepare('/root/sifter','/build/'+variant+('-logging' if logging else '-plain'),variant,logging,4)
                if logging:
                    invoke('rebuild_valkey_diagnostics.py',['--variant',variant])
        client=Path('/build/memtier')
        shutil.copytree('/root/sifter/artifact/vendor/memtier',client)
        for command in (['autoreconf','-ivf'],['./configure','--disable-tls'],['make','-j4']):
            subprocess.run(command,cwd=client,check=True)


def trial(cell):
    app,family,variant,arm,rep=(cell[k] for k in ('application','family','variant','arm','repetition'))
    data=Path('/campaign/data')
    dest=None
    if family in ('ascylib','tpcc'):
        import run_ascylib, run_tpcc
        manifest=json.loads(Path('/build/manifest.json').read_text())
        row=next(r for r in manifest['records'] if (r['application'],r['variant'],r['arm'])==(app.split('_')[1],variant,arm))
        out=data/(family+'-paper');out.mkdir(exist_ok=True)
        store=TraceStore(raw_root=data/'raw-paper-v2',archive_root=Path('/campaign/archive/archives-paper-v2'),
            manifest_root=data/'trace-manifests-paper-v2',campaign='portable-headline',host=os.environ['HL_HOST'],
            expected_traces=expected_traces(('ascylib','tpcc','rocks')))
        if family=='ascylib':result=run_ascylib.run_one(row,rep,False,store,out)
        else:result=run_tpcc.trial(row,rep,store,out)
        dest=out/result['trial_id']
    elif family=='rocks':
        invoke('run_rocks.py',['--app',app.split('_')[1],'--variant',variant,'--arm',arm,'--rep',str(rep),'--raw-cap-gib','30'])
        dest=data/'rocks-paper'/f'paper-rocks-{app.split("_")[1]}-{variant}-{arm}-r{rep:02d}'
        if app=='rocks_hsl':
            import retain_hsl_db
            retain_hsl_db.archive_db(dest.name)
    else:
        variant={'before':'baseline','after':'optimized'}[variant]
        if family=='valkey':
            client=Path('/build/memtier/memtier_benchmark')
            invoke('run_valkey.py',['--variant',variant,'--arm',arm,'--rep',str(rep),
                '--client',str(client),'--client-sha256',sha(client)])
            dest=data/'valkey-paper'/f'paper-valkey-{variant}-{arm}-r{rep:02d}'
            import audit_valkey
            checked=audit_valkey.audit(dest)
            if arm=='logging':invoke('retain_valkey.py',[dest.name])
            else:write_json(dest/'measurement-audit.json',checked)
        elif family=='hnsw':
            dim=int(app[4:]);dest=data/'hnsw-paper'/f'paper-hnsw-d{dim}-{variant}-{arm}-r{rep:02d}'
            invoke('smoke_hnsw.py',['--headline','--variant',variant,'--arm',arm,'--dim',str(dim),
                '--rep',str(rep),'--output',str(dest)])
            import audit_hnsw
            checked=audit_hnsw.audit(dest)
            if arm=='logging':invoke('retain_hnsw.py',[dest.name])
            else:write_json(dest/'measurement-audit.json',checked)
    # Require high PMU coverage for every family before accepting this cell.
    from audit_valkey import counter_rows
    counters=counter_rows(dest/'perf.csv')
    write_json(dest/'portable-completed.json',dict(cell=cell,pmu=counters,
        result_sha256=sha(dest/'result.json'),status='measurement_and_retention_completed'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['build','trial'])
    parser.add_argument('payload')
    args=parser.parse_args()
    value=json.loads(args.payload)
    if args.action=='build':build(value['family'],value['apps'])
    else:trial(value)


if __name__=='__main__':main()
