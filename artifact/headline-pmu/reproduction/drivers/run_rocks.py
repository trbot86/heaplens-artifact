"""One full-size headline RocksDB cell; caller owns serialization and build mount.

Initial cells are repetition 1 of the final campaign, not disposable smokes.
This driver preserves database files and stops at storage guards; no DB cleanup.
"""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
from portable_runtime import expected_traces
import argparse,hashlib,json,os,shutil,signal,subprocess,sys,time
from pathlib import Path
from trace_store import TraceStore,GIB,write_json,sha
from run_ascylib import HOME,SCRATCH,REV,EVENTS,counters
from rocks_measurement import parse_reader_result,check_isl_topology
sys.path.insert(0,'/root/sifter/artifact')
from lib import rocksdb_hashskiplist as hsl, rocksdb_memoryonly as isl

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--app',choices=['hsl','isl'],required=True)
    parser.add_argument('--variant',choices=['before','after'],required=True)
    parser.add_argument('--arm',choices=['plain','logging'],required=True)
    parser.add_argument('--rep',type=int,choices=range(1,11),required=True)
    parser.add_argument('--raw-cap-gib',type=int,choices=[20,30],default=20)
    args=parser.parse_args();build=Path('/build');root=Path('/root/sifter/artifact')
    manifest=json.loads((build/f'manifest-{args.app}-{args.variant}.json').read_text())
    row=next(r for r in manifest['records'] if r['arm']==args.arm)
    assert row['application']==args.app and row['variant']==args.variant
    assert sha(row['path'])==row['sha256']
    logger=build/'wait-memhook/libmemhook.so'
    assert sha(logger)==manifest['logger_sha256']
    allocator=root/'vendor/heaplens-allocators/libjemalloc-heaplens.so'
    env=isl.environment(allocator)
    for key in ['MALLOC_CONF','MEMHOOK_OUTPUT_DUMP_FILE','MEMHOOK_OUTPUT_TYPE_FILE']:
        env.pop(key,None)
    name=f'paper-rocks-{args.app}-{args.variant}-{args.arm}-r{args.rep:02d}'
    out=HOME/'rocks-paper';out.mkdir(exist_ok=True)
    dest=out/name;dest.mkdir()
    store=TraceStore(raw_root=HOME/'raw-paper-v2',archive_root=SCRATCH/'archives-paper-v2',
        manifest_root=HOME/'trace-manifests-paper-v2',campaign='portable-headline',host=host_name(),
        expected_traces=expected_traces(('ascylib','tpcc','rocks')))
    raw_cap=args.raw_cap_gib*GIB
    # HSL also retains database tables on NFS; reserve 5 GiB beyond the trace.
    store.before_trial(raw_cap+(5*GIB if args.app=='hsl' else 0))
    raw=store.raw_root/name;logging=args.arm=='logging'
    if logging:raw.mkdir()
    ctl,ack=dest/'perf-control',dest/'perf-ack';os.mkfifo(ctl);os.mkfifo(ack)
    env.update(HL_PERF_CONTROL=str(ctl),HL_PERF_ACK=str(ack))
    preload=([str(logger)] if logging else [])+[str(allocator)]
    # Set allocator/logger only on db_bench, not perf, prlimit or numactl.
    env.pop('LD_PRELOAD',None)
    assignments=['LD_PRELOAD='+':'.join(preload)]
    if logging:assignments+=['MEMHOOK_OUTPUT_DUMP_FILE='+str(raw/'events.bin'),
                             'MEMHOOK_OUTPUT_TYPE_FILE='+str(raw/'typeset-runtime.txt')]
    options=dest/'rocksdb-options.ini';option_hash=None
    if args.app=='hsl':
        threads,duration=96,10
        placement=['numactl','--physcpubind='+rocks_cpus(),'--interleave='+','.join(map(str,rocks_nodes()))]
        hsl.cpus(rocks_nodes(),96,rocks_cpus())
        benchmarks='filluniquerandom,waitforcompaction,readwhilewriting'
        workload=hsl.workload_args(threads)
    else:
        threads,duration=20,60;isl.check_memory()
        cpus(20)  # physical-core topology was validated by the portable preflight
        placement=['numactl','--physcpubind='+cpus(20),'--membind='+str(node(0))]
        benchmarks='filluniquerandom,readwhilewriting'
        option_hash=isl.write_options(root/'config/rocksdb-memoryonly/skip_list.ini',options,threads,32)
        workload=['--options_file='+str(options)]
    bench=[row['path'],'--db='+str(dest/'db'),'--use_existing_db=0','--benchmarks='+benchmarks,
           '--key_size=32','--prefix_size=32','--value_size=128','--num=10000000',
           f'--threads={threads-1}','--disable_wal=1','--sync=0',f'--duration={duration}',*workload]
    cmd=['perf','stat','-D','-1','--control=fifo:'+str(ctl)+','+str(ack),'-x,','-e',EVENTS,
         '-o',str(dest/'perf.csv'),'--','prlimit','--fsize='+str(raw_cap)+':'+str(raw_cap),'--',
         *placement,'env',*assignments,*bench]
    identity=dict(trial_id=name,application='rocks_'+args.app,variant=args.variant,arm=args.arm,
        repetition=args.rep,source_revision=REV,binary_sha256=row['sha256'],
        command_sha256=hashlib.sha256(json.dumps(cmd).encode()).hexdigest())
    write_json(dest/'command.json',dict(command=cmd,cwd=row['cwd'],identity=identity,build=row,
        allocator_sha256=sha(allocator),logger_sha256=sha(logger),options_sha256=option_hash,raw_cap_bytes=raw_cap,
        wait_scope='Benchmark workers only in phase 1; background-worker phase 0 is not initialization-only',
        environment={k:env.get(k) for k in ['GLIBC_TUNABLES','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MALLOC_CONF']}))
    start=time.monotonic()
    with (dest/'benchmark.log').open('x') as log:
        proc=subprocess.Popen(cmd,cwd=row['cwd'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while proc.poll() is None:
                if time.monotonic()-start>7200:raise RuntimeError('Two-hour trial guard')
                if min(shutil.disk_usage(HOME).free,shutil.disk_usage(SCRATCH).free)<50*GIB:raise RuntimeError('Storage floor')
                time.sleep(1)
            if proc.returncode:raise RuntimeError(f'RocksDB exit {proc.returncode}')
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=20)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    text=(dest/'benchmark.log').read_text()
    result=parse_reader_result(text);pmu=counters(dest/'perf.csv')
    for token in ['aio_write FAILED','aio_suspend failed','Error in `dlsym`']:
        if token in text:raise ValueError(token)
    persistence=hsl.validate(dest,threads,32) if args.app=='hsl' else isl.validate(dest,options)
    write_json(dest/'persistence.json',persistence)
    for value in pmu.values():value['per_operation']=value['scaled_count']/result['operation_count']
    waits=[json.loads(line[8:]) for line in text.splitlines() if line.startswith('HL_WAIT ')]
    if logging:
        measured={r['tid'] for r in waits if r['phase']==1 and r['begin_ns']>0 and r['end_ns']>=r['begin_ns']}
        assert len(measured)==threads,(name,len(measured),threads)
        assert not any(r['reuse_errors'] or r['shutdown_errors'] for r in waits)
        for sidecar in ['typeset_dump.txt','fileset_dump.txt','fielddump.txt']:
            src=Path(row['cwd'])/sidecar
            if src.exists():shutil.copy2(src,raw/sidecar)
    else:assert not waits
    assert sha(row['path'])==row['sha256'] and sha(allocator)==isl.ALLOCATOR_SHA256
    identity['measurement_status']='completed'
    write_json(dest/'result.json',dict(**identity,**result,pmu=pmu,waits=waits,process_wall_seconds=time.monotonic()-start))
    if logging:store.archive(name,identity)
    time.sleep(15)

if __name__=='__main__':main()
