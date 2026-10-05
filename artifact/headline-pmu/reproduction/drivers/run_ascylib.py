"""Fixed before/after x plain/logging sequence, measured PMU phase, retained traces."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from trace_store import TraceStore, GIB, write_json, sha

HOME=Path('/campaign/data')
SCRATCH=Path('/campaign/archive')
BUILD=Path('/build')
REV='7f4f5f20125ad0a2571abc8ddb0e98e13c7ae109'
EVENTS='cycles,instructions,cache-misses,dTLB-load-misses'
sys.path.insert(0,'/root/sifter/artifact/lib')
from perfstat_results import parse_benchmark

def schedule(reps):
    cells=[('before','plain'),('before','logging'),('after','plain'),('after','logging')]
    rows=[]
    for r in range(reps):
        block=cells[r%4:]+cells[:r%4]
        if (r//4)%2:block=block[::-1]
        rows.extend((app,v,a,r+1) for app in ['efrb','dvy','hj'] for v,a in block)
    return rows

def counters(path):
    import csv
    from audit_valkey import counter_rows
    counter_rows(path)  # fail before retention if coverage/support is inadequate
    values={}
    for row in csv.reader(path.read_text().splitlines()):
        if len(row)<3 or row[2].strip() not in EVENTS.split(','):continue
        name=row[2].strip()
        if name in values:raise ValueError('Duplicate counter '+name)
        try:value=float(row[0])
        except ValueError:raise ValueError('Counter not available: '+repr(row))
        if value<0:raise ValueError('Negative counter')
        values[name]={'scaled_count':value,'perf_fields':row}
    if set(values)!=set(EVENTS.split(',')):raise ValueError('Missing counters')
    return values

def run_one(row,rep,smoke,store,out):
    app,v,arm=row['application'],row['variant'],row['arm']
    trial_id=f'{"smoke" if smoke else "paper"}-{app}-{v}-{arm}-r{rep:02d}'
    trial=out/trial_id;trial.mkdir()
    rawdir=store.raw_root/trial_id
    if arm=='logging':rawdir.mkdir()
    store.before_trial(20*GIB)
    ctl,ack=trial/'perf-control',trial/'perf-ack'
    os.mkfifo(ctl);os.mkfifo(ack)
    env=os.environ.copy()
    for key in ['LD_PRELOAD','LD_LIBRARY_PATH','GLIBC_TUNABLES','MALLOC_CONF']:env.pop(key,None)
    env.update(HL_PERF_CONTROL=str(ctl),HL_PERF_ACK=str(ack))
    preload=[str(BUILD/'ssmem/libssmem_x86_64.so')]
    if arm=='logging':preload.insert(0,str(BUILD/'wait-memhook/libmemhook.so'))
    if app=='hj' and v=='before':preload.append('/root/sifter/artifact/vendor/heaplens-allocators/libjemalloc-heaplens.so')
    assignments=['LD_PRELOAD='+':'.join(preload),'LD_LIBRARY_PATH='+str(BUILD/'ssmem')]
    if arm=='logging':assignments.extend(['MEMHOOK_OUTPUT_DUMP_FILE='+str(rawdir/'events.bin'),
                                        'MEMHOOK_OUTPUT_TYPE_FILE='+str(rawdir/'typeset-runtime.txt')])
    runtime=[]
    if app=='dvy':
        assignments+=['GLIBC_TUNABLES=glibc.malloc.hugetlb=1']
        runtime=['/opt/heaplens-dvy-runtime/ld-linux-x86-64.so.2','--inhibit-cache','--library-path',
                 '/opt/heaplens-dvy-runtime:/build/ssmem:/build/wait-memhook']
    initial=4096 if smoke else row['initial']
    duration=1000 if smoke else 5000
    cmd=['numactl','--physcpubind='+cpus(row['threads']),'--'+row['memory']+'='+str(node(0)),'env',
         *assignments,*runtime,row['path'],'-i',str(initial),'-r',str(initial*2),'-n',str(row['threads']),'-u','0','-d',str(duration)]
    assert sha(row['path'])==row['sha256']
    measured=['perf','stat','-D','-1','--control=fifo:'+str(ctl)+','+str(ack),'-x,','-e',EVENTS,'-o',str(trial/'perf.csv'),
              '--','prlimit','--fsize='+str(20*GIB)+':'+str(20*GIB),'--',*cmd]
    identity=dict(trial_id=trial_id,application='ascylib_'+app,variant=v,repetition=rep,arm=arm,
        source_revision=REV,binary_sha256=row['sha256'],command_sha256=hashlib.sha256(json.dumps(measured).encode()).hexdigest())
    write_json(trial/'command.json',dict(identity=identity,command=measured,
        environment={k:env.get(k) for k in ['HL_PERF_CONTROL','HL_PERF_ACK','LD_PRELOAD','LD_LIBRARY_PATH','GLIBC_TUNABLES','MALLOC_CONF']},cwd=row['cwd'],
        counter_scope='After all prefills, before releasing operation-loop barrier; ends after all operation loops exit, before teardown.',
        workload=dict(initial=initial,range=initial*2,threads=row['threads'],update_pct=0,duration_ms=duration),
        allocator_files={p:sha(p) for p in preload},logger_sha256=sha(BUILD/'wait-memhook/libmemhook.so')))
    start=time.monotonic()
    with (trial/'benchmark.log').open('x') as log:
        proc=subprocess.Popen(measured,env=env,cwd=row['cwd'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while proc.poll() is None:
                if time.monotonic()-start>900:raise RuntimeError('Trial timeout')
                if min(shutil.disk_usage(HOME).free,shutil.disk_usage(SCRATCH).free)<50*GIB:
                    raise RuntimeError('Storage floor reached; preserve incomplete trial')
                time.sleep(1)
            if proc.returncode:raise RuntimeError('Trial failed: '+str(proc.returncode))
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=20)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    text=(trial/'benchmark.log').read_text()
    for term in ['aio_write FAILED','aio_suspend failed','Error in `dlsym`','WRONG size']:
        if term in text:raise ValueError(term)
    assert text.count('HL_COUNTER_GATE enable')==1 and text.count('HL_COUNTER_GATE disable')==1
    count,rate,unit=parse_benchmark(text,'ascylib')
    pmu=counters(trial/'perf.csv')
    for val in pmu.values():val['per_operation']=val['scaled_count']/count
    waits=[json.loads(line[8:]) for line in text.splitlines() if line.startswith('HL_WAIT ')]
    if arm=='logging':
        measured_threads={r['tid'] for r in waits if r['phase']==1 and r['begin_ns']>0 and r['end_ns']>=r['begin_ns']}
        assert len(measured_threads)==row['threads'],(trial_id,len(measured_threads),row['threads'])
        assert not any(r['reuse_errors'] or r['shutdown_errors'] for r in waits)
        for name in ['fileset_dump.txt','typeset_dump.txt','fielddump.txt']:
            src=Path(row['cwd'])/name
            if src.exists():shutil.copy2(src,rawdir/name)
    else:assert not waits
    identity['measurement_status']='completed'
    result=dict(**identity,operation_count=count,operation_unit=unit,throughput=float(rate),
                process_wall_seconds=time.monotonic()-start,pmu=pmu,waits=waits,smoke=smoke)
    write_json(trial/'result.json',result)
    assert sha(row['path'])==row['sha256']
    if arm=='logging':store.archive(trial_id,identity)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
    suffix=os.environ.get('HL_ATTEMPT','')
    assert re.fullmatch(r'[a-z0-9-]*',suffix)
    out=HOME/(('ascylib-smoke' if args.smoke else 'ascylib-paper')+suffix);out.mkdir()
    prefix=('smoke' if args.smoke else 'paper')+suffix
    store=TraceStore(raw_root=HOME/('raw-'+prefix),archive_root=SCRATCH/('archives-'+prefix),
        manifest_root=HOME/('trace-manifests-'+prefix),campaign='headline-'+prefix,host=host_name(),expected_traces=6 if args.smoke else 200)
    manifest=json.loads((BUILD/'manifest.json').read_text())
    rows={(r['application'],r['variant'],r['arm']):r for r in manifest['records']}
    order=schedule(1 if args.smoke else 10)
    write_json(out/'protocol.json',dict(sequence=order,events=EVENTS,source=REV,build_manifest=manifest,
        scope='ASCYLIB subset of headline campaign; other applications remain separate.'))
    state=dict(status='running',completed=0,total=len(order));write_json(out/'state.json',state)
    try:
        for app,v,arm,rep in order:
            state['active']=[app,v,arm,rep];write_json(out/'state.json',state)
            result=run_one(rows[app,v,arm],rep,args.smoke,store,out)
            print(result['trial_id'],result['throughput'],flush=True)
            state['completed']+=1;write_json(out/'state.json',state)
            time.sleep(2)
        state.update(status='completed');write_json(out/'state.json',state)
    except BaseException as exc:
        state.update(status='failed',error=repr(exc));write_json(out/'state.json',state);raise
if __name__=='__main__':main()
