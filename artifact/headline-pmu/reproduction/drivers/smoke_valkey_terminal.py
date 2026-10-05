"""Native integration smoke only: not a headline measurement or accepted cell."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import shutil
import argparse
from concurrent.futures import ThreadPoolExecutor

BUILD = Path('/build/baseline-logging')
OUT = Path('/campaign/data/valkey-terminal-smoke3')


def request(sock, *args):
    args = [str(a).encode() for a in args]
    sock.sendall(b'*'+str(len(args)).encode()+b'\r\n'+b''.join(
        b'$'+str(len(a)).encode()+b'\r\n'+a+b'\r\n' for a in args))
    result=b''
    while not result.endswith(b'\r\n'):
        part=sock.recv(1)
        if not part:
            raise RuntimeError('unexpected EOF')
        result += part
    return result


def main():
    global BUILD, OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--variant',choices=['baseline','optimized'],default='baseline')
    parser.add_argument('--output-name',default='valkey-terminal-smoke3')
    parser.add_argument('--concurrent-diagnostic',action='store_true')
    parser.add_argument('--pipeline-diagnostic',action='store_true')
    args=parser.parse_args()
    if not args.output_name.startswith('valkey-terminal-smoke') or not args.output_name.replace('-','').isalnum():
        raise ValueError('invalid output name')
    BUILD=Path('/build')/(args.variant+'-logging')
    OUT=OUT.parent/args.output_name
    OUT.mkdir(exist_ok=False)
    if shutil.disk_usage(OUT).free < 50*1024**3:
        raise RuntimeError('Storage floor')
    server=BUILD/'work-valkey/src/valkey-server'
    command=['numactl','--physcpubind='+cpus(24),'--membind='+str(node(0)),str(server),
             '--bind','127.0.0.1','--port','16379','--save','','--appendonly','no',
             '--daemonize','no','--dir',str(OUT),'--io-threads','24',
             '--io-threads-always-active','yes','--enable-debug-command','yes']
    env=dict(os.environ, LD_PRELOAD=str(BUILD/'toolchain/memhook/libmemhook.so'),
             MEMHOOK_OUTPUT_DUMP_FILE=str(OUT/'binary_dump.txt'))
    result=dict(scope=('memtier 24x4 clients, pipeline16, 10000 SET requests/client diagnostic' if args.pipeline_diagnostic else
                       '96 connections x 100 SET readiness diagnostic' if args.concurrent_diagnostic else
                       '2000-key terminal integration smoke')+'; not headline evidence',command=command,status='running')
    (OUT/'result.json').write_text(json.dumps(result,indent=2))
    with (OUT/'server.log').open('w') as log:
        proc=subprocess.Popen(command,env=env,cwd=OUT,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+60
            while True:
                if proc.poll() is not None: raise RuntimeError('server exited '+str(proc.returncode))
                try:
                    sock=socket.create_connection(('127.0.0.1',16379),timeout=2)
                    break
                except OSError:
                    if time.monotonic()>deadline: raise
                    time.sleep(.1)
            with sock:
                sock.settimeout(130)
                assert request(sock,'PING')==b'+PONG\r\n'
                lo=time.monotonic_ns()
                if args.pipeline_diagnostic:
                    cmd=['numactl','--physcpubind='+cpus(24,1),'--membind='+str(node(1)),'/client/memtier_benchmark',
                         '--server=127.0.0.1','--port=16379','--protocol=redis','--threads=24',
                         '--clients=4','--pipeline=16','--ratio=1:0','--key-pattern=R:R',
                         '--key-minimum=1','--key-maximum=20000','--data-size=128',
                         '--distinct-client-seed','--hide-histogram','--requests=10000']
                    with (OUT/'client.log').open('x') as client_log:
                        subprocess.run(cmd,stdout=client_log,stderr=subprocess.STDOUT,timeout=60,check=True)
                elif args.concurrent_diagnostic:
                    def worker(index):
                        with socket.create_connection(('127.0.0.1',16379),timeout=10) as client:
                            client.settimeout(30)
                            for i in range(100):
                                if request(client,'SET','diag:%d:%d'%(index,i),'x'*128)!=b'+OK\r\n':
                                    raise RuntimeError('diagnostic SET failed')
                    with ThreadPoolExecutor(max_workers=96) as pool:
                        list(pool.map(worker,range(96)))
                else:
                    for i in range(2000):
                        assert request(sock,'SET','heaplens:'+str(i),'x'*128)==b'+OK\r\n'
                hi=time.monotonic_ns()
                # Diagnostic window only; no PMU or throughput claim.
                replies=[]
                for attempt in range(30):
                    reply=request(sock,'DEBUG','heaplens-finish',lo,hi)
                    replies.append(reply.decode())
                    if reply==b'+OK\r\n': break
                    time.sleep(.1)
                else: raise RuntimeError('terminal command not ready: '+repr(replies))
                result.update(lo=lo,hi=hi,terminal_replies=replies)
                sock.sendall(b'*2\r\n$8\r\nSHUTDOWN\r\n$6\r\nNOSAVE\r\n')
            if proc.wait(timeout=60)!=0: raise RuntimeError('shutdown failed')
            reports=[]
            producers=[]
            for line in (OUT/'server.log').read_text(errors='replace').splitlines():
                if line.startswith('HL_WINDOW_WAIT '): reports.append(json.loads(line[15:]))
                if line.startswith('HL_PRODUCER '): producers.append(json.loads(line[12:]))
            tids={r['tid'] for r in reports}
            if len(tids)!=29 or len(reports)!=58:
                raise RuntimeError('expected main+23 IO+5 BIO reports, got '+str((len(tids),len(reports))))
            if any(sorted(r['kind'] for r in reports if r['tid']==tid)!=[0,1] for tid in tids):
                raise RuntimeError('duplicate/missing kinds')
            size=(OUT/'binary_dump.txt').stat().st_size
            if size<=0: raise RuntimeError('empty trace')
            if len(producers)!=29 or {p['tid'] for p in producers}!=tids:
                raise RuntimeError('producer report set mismatch')
            if sum(p['records']*p['record_bytes'] for p in producers)!=size:
                raise RuntimeError('raw bytes do not reconcile with producer record totals')
            result.update(status='passed_integration_only',reports=reports,producers=producers,raw_bytes=size)
        except BaseException as error:
            result.update(status='failed',error=repr(error))
            raise
        finally:
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=20)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
            (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__': main()
