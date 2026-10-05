"""TPC-C headline PMU/logging cells, with no attribution cells or stock-logger arm."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from trace_store import TraceStore, GIB, write_json, sha
from run_ascylib import HOME,SCRATCH,REV,EVENTS,counters,parse_benchmark

BUILD=Path('/build')
def sequence():
    cells=[('before','plain'),('before','logging'),('after','plain'),('after','logging')]
    for rep in range(10):
        block=cells[rep%4:]+cells[:rep%4]
        if (rep//4)%2:block=block[::-1]
        for app in ['bcco','efrb']:
            for variant,arm in block:yield app,variant,arm,rep+1
def trial(row,rep,store,out):
    name=f'paper-tpcc-{row["application"]}-{row["variant"]}-{row["arm"]}-r{rep:02d}'
    dest=out/name;dest.mkdir();rawdir=store.raw_root/name
    logging=row['arm']=='logging'
    store.before_trial(20*GIB)
    if logging:rawdir.mkdir()
    ctl,ack=dest/'perf-control',dest/'perf-ack';os.mkfifo(ctl);os.mkfifo(ack)
    clean=dict(os.environ)
    for key in ['LD_PRELOAD','LD_LIBRARY_PATH','GLIBC_TUNABLES','MALLOC_CONF']:clean.pop(key,None)
    clean.update(HL_PERF_CONTROL=str(ctl),HL_PERF_ACK=str(ack))
    preload=([str(BUILD/'wait-memhook/libmemhook.so')] if logging else [])+[row['allocator']]
    assert sha(row['path'])==row['sha256'] and sha(row['allocator'])==row['allocator_sha256']
    envargs=['LD_PRELOAD='+':'.join(preload),'GLIBC_TUNABLES=glibc.rtld.optional_static_tls=4194304']
    if logging:envargs+=['MEMHOOK_OUTPUT_DUMP_FILE='+str(rawdir/'events.bin'),
                        'MEMHOOK_OUTPUT_TYPE_FILE='+str(rawdir/'typeset-runtime.txt')]
    cmd=['perf','stat','-D','-1','--control=fifo:'+str(ctl)+','+str(ack),'-x,','-e',EVENTS,'-o',str(dest/'perf.csv'),
         '--','prlimit','--fsize='+str(20*GIB)+':'+str(20*GIB),'--','numactl','--physcpubind='+cpus(24),'--membind='+str(node(0)),
         'env',*envargs,row['path'],'-pin',cpus(24)]
    identity=dict(trial_id=name,application='tpcc_'+row['application'],variant=row['variant'],arm=row['arm'],repetition=rep,
        source_revision=REV,binary_sha256=row['sha256'],command_sha256=hashlib.sha256(json.dumps(cmd).encode()).hexdigest())
    write_json(dest/'command.json',dict(command=cmd,cwd=row['cwd'],identity=identity,build=row,
        counter_scope='Measured transaction thread creation through joins; excludes database population and warmup.',
        wait_scope='Each measured worker thread_t::run call, excluding index-thread initialization and deinitialization.',
        logger_sha256=sha(BUILD/'wait-memhook/libmemhook.so'),
        environment={k:clean.get(k) for k in ['HL_PERF_CONTROL','HL_PERF_ACK','LD_PRELOAD','GLIBC_TUNABLES']}))
    start=time.monotonic()
    with (dest/'benchmark.log').open('x') as log:
        proc=subprocess.Popen(cmd,cwd=row['cwd'],env=clean,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while proc.poll() is None:
                if time.monotonic()-start>1800:raise RuntimeError('TPC-C trial exceeded 30-minute guard')
                if min(shutil.disk_usage(HOME).free,shutil.disk_usage(SCRATCH).free)<50*GIB:raise RuntimeError('Storage floor')
                time.sleep(1)
            if proc.returncode:raise RuntimeError('TPC-C failed: '+str(proc.returncode))
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=20)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    text=(dest/'benchmark.log').read_text()
    assert text.count('HL_COUNTER_GATE enable')==1 and text.count('HL_COUNTER_GATE disable')==1
    for token in ['aio_write FAILED','aio_suspend failed','Error in `dlsym`']:
        if token in text:raise ValueError(token)
    count,rate,unit=parse_benchmark(text,'tpcc')
    pmu=counters(dest/'perf.csv')
    for value in pmu.values():value['per_operation']=value['scaled_count']/count
    waits=[json.loads(line[8:]) for line in text.splitlines() if line.startswith('HL_WAIT ')]
    if logging:
        measured={r['tid'] for r in waits if r['phase']==1 and r['begin_ns']>0 and r['end_ns']>=r['begin_ns']}
        assert len(measured)==24,(name,len(measured))
        assert not any(r['reuse_errors'] or r['shutdown_errors'] for r in waits)
        for sidecar in ['typeset_dump.txt','fileset_dump.txt','fielddump.txt']:
            src=Path(row['cwd'])/sidecar
            if src.exists():shutil.copy2(src,rawdir/sidecar)
    else:assert not waits
    identity['measurement_status']='completed'
    result=dict(**identity,throughput=float(rate),operation_count=count,operation_unit=unit,
                pmu=pmu,waits=waits,process_wall_seconds=time.monotonic()-start)
    write_json(dest/'result.json',result)
    assert sha(row['path'])==row['sha256'] and sha(row['allocator'])==row['allocator_sha256']
    if logging:store.archive(name,identity)
    return result
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pilot',action='store_true',help='Run exactly the first full-size repetition, then stop for independent validation.')
    args=parser.parse_args()
    out=HOME/'tpcc-paper';out.mkdir()
    store=TraceStore(raw_root=HOME/'raw-paper-v2',archive_root=SCRATCH/'archives-paper-v2',manifest_root=HOME/'trace-manifests-paper-v2',
        campaign='headline-paper-v2',host=host_name(),expected_traces=200)
    manifest=json.loads((BUILD/'manifest.json').read_text())
    records={(r['application'],r['variant'],r['arm']):r for r in manifest['records']}
    order=list(sequence())
    write_json(out/'protocol.json',dict(sequence=order,events=EVENTS,build_manifest=manifest,
        pilot_included_in_final_results=True,validation_gate_after_trials=8))
    if args.pilot:order=order[:8]
    state=dict(status='running',completed=0,total=len(order));write_json(out/'state.json',state)
    try:
        for app,v,arm,rep in order:
            state['active']=[app,v,arm,rep];write_json(out/'state.json',state)
            result=trial(records[app,v,arm],rep,store,out)
            state['completed']+=1;write_json(out/'state.json',state)
            print(result['trial_id'],result['throughput'],flush=True);time.sleep(2)
        state.update(status='pilot_complete_validation_pending' if args.pilot else 'completed');write_json(out/'state.json',state)
    except BaseException as e:
        state.update(status='failed',error=repr(e));write_json(out/'state.json',state);raise
if __name__=='__main__':main()
