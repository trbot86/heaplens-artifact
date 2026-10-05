"""One full headline-size cell. DRAFT: not yet native-validated.

Caller owns host lock, verifies build mounts/identities and serial execution.
Raw output is retained on NFS; archival is a separate between-cell action.
"""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
from valkey_protocol import PerfGate, client_command
from smoke_valkey_terminal import request

HOME=Path('/campaign/data')
EVENTS='cycles,instructions,cache-misses,dTLB-load-misses'
GIB=1024**3


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--variant',choices=['baseline','optimized'],required=True)
    parser.add_argument('--arm',choices=['plain','logging'],required=True)
    parser.add_argument('--rep',type=int,choices=range(1,11),required=True)
    parser.add_argument('--client',type=Path,required=True)
    parser.add_argument('--client-sha256',required=True)
    args=parser.parse_args()
    if digest(args.client)!=args.client_sha256:
        raise RuntimeError('client identity mismatch')
    child_env=os.environ.copy()
    for key in ('LD_PRELOAD','LD_LIBRARY_PATH','GLIBC_TUNABLES','MALLOC_CONF'):
        child_env.pop(key,None)
    name='paper-valkey-'+args.variant+'-'+args.arm+'-r%02d'%args.rep
    dest=HOME/'valkey-paper'/name
    dest.mkdir(parents=True,exist_ok=False)
    build=Path('/build')/(args.variant+'-'+args.arm)
    manifest=json.loads((build/'preparation.json').read_text())
    if manifest['status']!='built_not_native_validated': raise RuntimeError('unexpected build status')
    for binary, expected in manifest['binaries'].items():
        if digest(binary)!=expected: raise RuntimeError('binary identity mismatch')
    cap=30*GIB
    def guard():
        if min(shutil.disk_usage(HOME).free,shutil.disk_usage('/build').free)<50*GIB:
            raise RuntimeError('storage safety floor')
    guard()
    if min(shutil.disk_usage(HOME).free,shutil.disk_usage('/build').free)<50*GIB+cap:
        raise RuntimeError('insufficient raw/archive reserve')
    ctl,ack=dest/'perf-control',dest/'perf-ack'
    os.mkfifo(ctl); os.mkfifo(ack)
    gate=PerfGate(ctl,ack)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0)); port=probe.getsockname()[1]
    server=build/'work-valkey/src/valkey-server'
    assignments=[]
    logging=args.arm=='logging'
    if logging:
        assignments=['LD_PRELOAD='+str(build/'toolchain/memhook/libmemhook.so'),
                     'MEMHOOK_OUTPUT_DUMP_FILE='+str(dest/'events.bin')]
    server_cmd=['numactl','--physcpubind='+cpus(24),'--membind='+str(node(0)),'env',*assignments,
                str(server),'--bind','127.0.0.1','--port',str(port),'--protected-mode','yes',
                '--save','','--appendonly','no','--daemonize','no','--dir',str(dest),
                '--io-threads','24','--io-threads-always-active','yes']
    if logging: server_cmd+=['--enable-debug-command','yes']
    command=['perf','stat','-D','-1','--control=fifo:'+str(ctl)+','+str(ack),
             '-x,','-e',EVENTS,'-o',str(dest/'perf.csv'),'--',
             'prlimit','--fsize='+str(cap)+':'+str(cap),'--',*server_cmd]
    preload=client_command(args.client,port,dest/'preload.json',True)
    measured=client_command(args.client,port,dest/'benchmark.json')
    state=dict(status='running',trial=name,variant=args.variant,arm=args.arm,rep=args.rep,
               server_command=command,preload_command=preload,client_command=measured,
               client_sha256=digest(args.client),build=manifest,raw_cap_bytes=cap,
               pmu_scope='server process and inherited threads; preload excluded; client startup/load/teardown enclosed',
               wait_scope='conservative enclosing monotonic gate bounds, including transition uncertainty')
    def save(): (dest/'result.json').write_text(json.dumps(state,indent=2)+'\n')
    save()
    def terminate(proc):
        if proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try: proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL); proc.wait(timeout=20)
    def client(cmd,label,limit,server_proc):
        with (dest/(label+'.log')).open('x') as log:
            proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=child_env)
            try:
                deadline=time.monotonic()+limit
                while proc.poll() is None:
                    guard()
                    if server_proc.poll() is not None: raise RuntimeError('server exited during '+label)
                    if time.monotonic()>deadline: raise TimeoutError(label)
                    time.sleep(.25)
                if proc.returncode: raise RuntimeError(label+' failed')
            finally: terminate(proc)
    with (dest/'server.log').open('x') as log:
        proc=subprocess.Popen(command,cwd=dest,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=child_env)
        try:
            deadline=time.monotonic()+60
            while True:
                guard()
                if proc.poll() is not None: raise RuntimeError('server startup failed')
                try:
                    sock=socket.create_connection(('127.0.0.1',port),timeout=.2)
                    break
                except OSError:
                    if time.monotonic()>deadline: raise
                    time.sleep(.1)
            with sock:
                sock.settimeout(130)
                if request(sock,'PING')!=b'+PONG\r\n': raise RuntimeError('PING failed')
                client(preload,'preload',1800,proc)
                state['enable']=gate.transition(True); save()
                client(measured,'benchmark',150,proc)
                state['disable']=gate.transition(False); save()
                totals=json.loads((dest/'benchmark.json').read_text())['ALL STATS']['Totals']
                if totals['Connection Errors']!=0 or totals['Misses/sec']!=0 or totals['Count']<=0:
                    raise RuntimeError('invalid workload outcome')
                state['client_totals']=totals
                if logging:
                    lo,hi=state['enable']['before_ns'],state['disable']['after_ns']
                    for _ in range(30):
                        reply=request(sock,'DEBUG','heaplens-finish',lo,hi)
                        if reply==b'+OK\r\n': break
                        time.sleep(.1)
                    else: raise RuntimeError('terminal handshake failed: '+repr(reply))
                sock.sendall(b'*2\r\n$8\r\nSHUTDOWN\r\n$6\r\nNOSAVE\r\n')
            if proc.wait(timeout=90): raise RuntimeError('perf/server shutdown failed')
            guard()
            state['status']='completed_pending_independent_audit'
            if logging:
                state['raw_bytes']=(dest/'events.bin').stat().st_size
        except BaseException as error:
            state.update(status='failed',error=repr(error)); raise
        finally:
            terminate(proc); gate.close(); save()


if __name__=='__main__': main()
