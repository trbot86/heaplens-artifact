"""Bounded Python-binding integration diagnostic, never headline evidence."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import argparse,json,os,subprocess,time,hashlib
from pathlib import Path
from audit_valkey import counter_rows, require

def main():
    p=argparse.ArgumentParser(); p.add_argument('--variant',required=True); p.add_argument('--arm',required=True)
    p.add_argument('--dim',type=int,choices=[128,1536],required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--headline',action='store_true');p.add_argument('--rep',type=int,choices=range(1,11),default=1)
    args=p.parse_args(); out=args.output;out.mkdir(parents=True,exist_ok=False)
    work=Path('/build')/(args.variant+'-'+args.arm)/'source'
    manifest=json.loads((work.parent/'preparation.json').read_text())
    for path,digest in manifest['binaries'].items():
        require(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,'binary identity')
    require(hashlib.sha256((work/'benchmark.py').read_bytes()).hexdigest()==manifest['benchmark_sha256'],'benchmark identity')
    require(hashlib.sha256((work/'python_bindings/bindings.cpp').read_bytes()).hexdigest()==manifest['binding_sha256'],'binding identity')
    elements,queries,warmup=(1000000,100000,10000) if args.headline else (2000,100,100)
    ctl=out/'control';ack=out/'ack';os.mkfifo(ctl);os.mkfifo(ack)
    env=os.environ.copy()
    for name in ('LD_PRELOAD','PYTHONPATH','GLIBC_TUNABLES'):env.pop(name,None)
    env.update(HL_PERF_CONTROL=str(ctl),HL_PERF_ACK=str(ack),OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1')
    if args.arm=='logging':
        env.update(LD_PRELOAD=str(work.parent/'toolchain/memhook/libmemhook.so'),
                   MEMHOOK_OUTPUT_DUMP_FILE=str(out/'events.bin'),MEMHOOK_OUTPUT_TYPE_FILE=str(out/'typeset_dump.txt'))
    # Apply preload only to Python, not perf/numactl.
    assignments=[k+'='+env[k] for k in ('HL_PERF_CONTROL','HL_PERF_ACK','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','PYTHONDONTWRITEBYTECODE')]
    if args.arm=='logging': assignments += [k+'='+env[k] for k in ('LD_PRELOAD','MEMHOOK_OUTPUT_DUMP_FILE','MEMHOOK_OUTPUT_TYPE_FILE')]
    command=['perf','stat','-D','-1','--control=fifo:'+str(ctl)+','+str(ack),'-x,','-e',
             'cycles,instructions,cache-misses,dTLB-load-misses','-o',str(out/'perf.csv'),'--',
             'numactl','--physcpubind='+cpus(24),'--membind='+str(node(0)),'env',*assignments,
             'python3','-u','benchmark.py','--probe','--dims',str(args.dim),
             '--variant-label',args.variant,'--variant-defines='+','.join(manifest['defines']),
             '--threads','24','--build-threads','24','--elements',str(elements),'--queries',str(queries),
             '--warmup',str(warmup),'--iterations','5','--m','16','--ef-construction','200','--ef','64','--k','10','--seed','1','--query-mode','indexed','--repetition',str(args.rep)]
    state=dict(status='running',scope='headline' if args.headline else '2000-element binding diagnostic; not headline evidence',command=command,
               build=manifest,variant=args.variant,arm=args.arm,dim=args.dim,rep=args.rep)
    def save(): (out/'result.json').write_text(json.dumps(state,indent=2)+'\n')
    save()
    try:
        clean=os.environ.copy();clean.pop('LD_PRELOAD',None)
        with (out/'stdout.log').open('x') as stdout,(out/'stderr.log').open('x') as stderr:
            subprocess.run(command,cwd=work,env=clean,stdout=stdout,stderr=stderr,timeout=28000 if args.headline else 180,check=True)
        lines=(out/'stderr.log').read_text().splitlines()
        windows=[json.loads(x[len('HL_HNSW_WINDOW '):]) for x in lines if x.startswith('HL_HNSW_WINDOW ')]
        workers=[json.loads(x[len('HL_HNSW_WORKER '):]) for x in lines if x.startswith('HL_HNSW_WORKER ')]
        require([x['iteration'] for x in windows]==list(range(1,6)),'five windows')
        for iteration in range(1,6):
            rows=[x for x in workers if x['iteration']==iteration and x['phase']==1]
            require(len(rows)==48,'24 worker boundaries')
            require({x['worker'] for x in rows}==set(range(24)),'worker identities')
        counters=counter_rows(out/'perf.csv')
        results=[json.loads(line) for line in (out/'stdout.log').read_text().splitlines()
                 if line.startswith('{') and '"timed_queries"' in line]
        require(len(results)==1,'one benchmark result despite logger banners')
        result=results[0]
        require(result['timed_queries']==queries*5,'actual denominator')
        state.update(status='passed_runner_checks' if args.headline else 'passed_gate_worker_integration_only',windows=windows,counters=counters,
                     worker_boundaries=len(workers),benchmark=result)
        if args.arm=='logging':
            waits=[json.loads(x[len('HL_WAIT '):]) for x in lines if x.startswith('HL_WAIT ')]
            size=(out/'events.bin').stat().st_size
            require(size>0 and size%40==0,'raw alignment')
            require(sum(x['records'] for x in waits)*40==size,'all producer byte reconciliation')
            measured={x['tid'] for x in workers if x['phase']==1}
            require(measured<={x['tid'] for x in waits if x['phase']==1},'measured producer completeness')
            require(all(x['reuse_errors']==x['shutdown_errors']==0 for x in waits),'wait errors')
            state.update(raw_bytes=size,wait_reports=waits)
    except BaseException as error:
        state.update(status='failed',error=repr(error));raise
    finally:save()

if __name__=='__main__':main()
