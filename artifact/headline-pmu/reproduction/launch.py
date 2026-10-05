#!/usr/bin/env python3
"""Explicit opt-in host controller for the historical 400-cell PMU campaign."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import time

from protocol import APPLICATIONS, REVISION, materialize, schedule, topology

BUNDLE=Path(__file__).resolve().parent
ROOT=BUNDLE.parents[2]
GIB=1024**3


def save(path,value):
    temporary=path.with_suffix('.json.tmp')
    with temporary.open('x') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


def digests():
    return {str(p.relative_to(BUNDLE)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(BUNDLE.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def storage(args):
    roots=[getattr(args,k) for k in ('work_root','data_root','archive_root')]
    if any(p is None for p in roots):raise ValueError('Specify all three absolute storage roots')
    for path in roots:
        if not path.is_absolute() or path.resolve()!=path or len(path.parts)<3 or ',' in str(path) or ':' in str(path):
            raise ValueError('Storage roots must be explicit absolute non-symlink Linux paths without commas/colons')
        if path==ROOT or path in ROOT.parents or ROOT in path.parents:
            raise ValueError('Keep campaign storage outside the source artifact')
    if any(a==b or a in b.parents or b in a.parents for i,a in enumerate(roots) for b in roots[i+1:]):
        raise ValueError('Storage roots must be separate and non-nested')
    return roots


def check_space(args,reserve=31*GIB):
    by_device={}
    for path in storage(args):
        probe=path
        while not probe.exists():probe=probe.parent
        key=probe.stat().st_dev
        # If live output and compressed archives share a filesystem, reserve
        # both sizes there. Never assume compression will create free space.
        by_device.setdefault(key,[probe,50*GIB])[1]+=reserve
    for path,needed in by_device.values():
        if shutil.disk_usage(path).free<needed:
            raise RuntimeError(f'Insufficient storage at {path}: need {needed/GIB:.1f} GiB free')


def container(args,image,name,family=None,perf=False):
    command=['docker','run','--rm','--init','--network','none','--name',name,
             '-e','PYTHONDONTWRITEBYTECODE=1','-e','HL_HOST='+socket.gethostname()]
    if perf:command+=['--cap-add','PERFMON','--security-opt','seccomp=unconfined',
                      '--ulimit',f'fsize={30*GIB}:{30*GIB}']
    for src,dst,readonly in ((BUNDLE,'/control',True),(args.work_root,'/campaign/work',False),
                             (args.data_root,'/campaign/data',False),(args.archive_root,'/campaign/archive',False)):
        command+=['--mount',f'type=bind,src={src},dst={dst}'+(',readonly' if readonly else '')]
    if family:
        command+=['--mount',f'type=bind,src={args.work_root / "source"},dst=/root/sifter',
                  '--mount',f'type=bind,src={args.work_root / "build" / family},dst=/build',
                  '-w','/root/sifter']
    return command+[image]


def bounded(command,log,name,seconds,args,deadline):
    process=None
    with log.open('x') as output:
        try:
            process=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT)
            stop=min(deadline,time.monotonic()+seconds)
            while process.poll() is None:
                if time.monotonic()>stop:raise TimeoutError('Bound reached; partial files retained')
                check_space(args,reserve=0)
                time.sleep(1)
            if process.returncode:raise RuntimeError(f'Stage failed ({process.returncode}); see {log}')
        finally:
            if process is not None and process.poll() is None:
                subprocess.run(['docker','stop','-t','20',name],timeout=35,check=False,
                               stdout=output,stderr=subprocess.STDOUT)
                try:process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    subprocess.run(['docker','kill',name],timeout=15,check=False,
                                   stdout=output,stderr=subprocess.STDOUT)
                    process.wait(timeout=20)


def preflight(args,image):
    command=['docker','run','--rm','--network','none','--cap-add','PERFMON',
             '--security-opt','seccomp=unconfined',image,'python3','-c',
             "import json,os,subprocess; print(json.dumps(dict(topology=subprocess.check_output(['lscpu','-p=CPU,NODE,SOCKET,CORE,ONLINE'],text=True),allowed=sorted(os.sched_getaffinity(0)))))"]
    raw=json.loads(subprocess.check_output(command,text=True,timeout=30))
    selected=topology(raw['topology'],set(raw['allowed']),args.server_node,args.client_node,args.apps)
    # Confirm actual event permission/support in this Docker configuration.
    # This bounded counter probe is not a performance observation.
    command[-3:]=['perf','stat','-x,','-e','cycles,instructions,cache-misses,dTLB-load-misses','--',
                  'python3','-c','import time; stop=time.monotonic()+0.3\nwhile time.monotonic()<stop: pass']
    probe=subprocess.run(command,text=True,capture_output=True,timeout=30)
    if probe.returncode or '<not ' in probe.stderr:
        raise RuntimeError('PMU preflight failed; no workload launched:\n'+probe.stderr)
    return dict(**selected,lscpu=raw['topology'],allowed=raw['allowed'],perf_probe=probe.stderr)


def collect_summary(args,plan):
    rows=[]
    for path in sorted(args.data_root.rglob('portable-completed.json')):
        receipt=json.loads(path.read_text());value=json.loads((path.parent/'result.json').read_text())
        if hashlib.sha256((path.parent/'result.json').read_bytes()).hexdigest()!=receipt['result_sha256']:
            raise ValueError('Completed cell changed')
        cell=receipt['cell'];family=cell['family']
        if family=='valkey':rate=value['client_totals']['Ops/sec']
        elif family=='hnsw':
            # Retain the exact native Python benchmark fields rather than
            # infer a rate from wall time or PMU duration.
            rate=value['benchmark']['qps_mean']
        else:rate=value['throughput']
        if not isinstance(rate,(int,float)) or not 0<rate<float('inf'):
            raise ValueError('Invalid native throughput')
        rows.append(dict(**cell,throughput=rate,result=str(path.parent/'result.json'),
                         source_revision=REVISION,pmu=receipt['pmu']))
    expected={c['id'] for c in plan}
    if len(rows)!=len(expected) or {r['id'] for r in rows}!=expected:
        raise ValueError('Incomplete or duplicate final cell identities')
    comparisons=[]
    for app in APPLICATIONS:
        for variant in ('before','after'):
            arms={arm:[r['throughput'] for r in rows if (r['application'],r['variant'],r['arm'])==(app,variant,arm)]
                  for arm in ('plain','logging')}
            if not arms['plain']:continue
            if len(arms['plain'])!=len(arms['logging']):raise ValueError('Unbalanced comparison')
            plain,logged=(statistics.mean(arms[arm]) for arm in ('plain','logging'))
            comparisons.append(dict(application=app,variant=variant,repetitions=len(arms['plain']),
                plain_mean=plain,logging_mean=logged,throughput_loss_pct=100*(1-logged/plain),raw=arms))
    save(args.work_root/'results.json',dict(scope='Fresh reproduction; never pooled with bundled observations',
        hsl_metric='Reader operations per native mixed-workload completion interval',rows=rows,comparisons=comparisons))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['plan','preflight','build','run'],nargs='?',default='plan')
    parser.add_argument('--apps',nargs='+',choices=APPLICATIONS,default=list(APPLICATIONS))
    parser.add_argument('--reps',type=int,default=10)
    for key in ('work-root','data-root','archive-root'):parser.add_argument('--'+key,type=Path)
    parser.add_argument('--image',default=os.environ.get('HEAPLENS_IMAGE','heaplens-atc26:submission'))
    parser.add_argument('--server-node',type=int,default=0)
    parser.add_argument('--client-node',type=int,default=1)
    parser.add_argument('--lock-file',type=Path,default=Path('/tmp/heaplens-headline-pmu.lock'))
    parser.add_argument('--timeout-hours',type=float,default=72)
    parser.add_argument('--acknowledge-cost',action='store_true',help='Accept >=48 hours and large retained storage for a full run')
    args=parser.parse_args(argv)
    plan=schedule(args.apps,args.reps)
    if args.action=='plan':
        print(json.dumps(dict(source_revision=REVISION,cells=len(plan),logging_cells=len(plan)//2,
            full_campaign=len(plan)==400,method='plain+PMU versus historical logger+wait probe+PMU',
            estimated_full_time='48 hours or more',observed_compressed_bytes=272941791880,
            sequence=plan),indent=2));return
    if sys.platform!='linux':parser.error('Run the controller in a Linux host shell')
    if sys.flags.optimize:parser.error('Do not disable Python assertions in historical validators')
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'Signal {signum}; stop the owned container and preserve this attempt')
    signal.signal(signal.SIGTERM,interrupted)
    if not args.acknowledge_cost:parser.error('Execution requires --acknowledge-cost; use plan for a read-only preview')
    if not 0<args.timeout_hours<=168:parser.error('Choose a positive bound of at most 168 hours')
    storage(args);check_space(args)
    import fcntl
    with args.lock_file.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        image=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',args.image],text=True,timeout=20).strip()
        if not re.fullmatch('sha256:[0-9a-f]{64}',image):raise ValueError('Cannot pin image identity')
        if args.action=='preflight':
            print(json.dumps(preflight(args,image),indent=2));return
        config=dict(apps=args.apps,reps=args.reps,image=image,server_node=args.server_node,client_node=args.client_node,
                    work_root=str(args.work_root),data_root=str(args.data_root),archive_root=str(args.archive_root),
                    source_revision=REVISION,inputs=digests(),plan=plan)
        if args.action=='build':
            for path in storage(args):
                if path.exists():raise FileExistsError('Fresh roots required; preserve existing attempt: '+str(path))
            for path in storage(args):path.mkdir(parents=True)
            save(args.work_root/'configuration.json',config)
            materialize(ROOT,BUNDLE,args.work_root/'source')
            (args.work_root/'build').mkdir()
            families=list(dict.fromkeys(c['family'] for c in plan))
            for family in families:(args.work_root/'build'/family).mkdir()
        else:
            if json.loads((args.work_root/'configuration.json').read_text())!=config:
                raise ValueError('Build configuration or scripts changed; preserve this attempt and prepare a fresh build')
            if json.loads((args.work_root/'build-state.json').read_text())['status']!='completed':
                raise ValueError('Build must complete first')
            if (args.work_root/'run-state.json').exists():raise FileExistsError('Never automatically resume or replay an attempted campaign')
            save(args.work_root/'topology.json',preflight(args,image))
        deadline=time.monotonic()+args.timeout_hours*3600
        state=dict(status='running',started=time.time(),completed=[],source_revision=REVISION)
        state_path=args.work_root/(args.action+'-state.json');save(state_path,state)
        name='heaplens-headline-'+hashlib.sha256(str(args.work_root).encode()).hexdigest()[:12]
        try:
            tasks=[dict(family=f,apps=args.apps) for f in families] if args.action=='build' else plan
            for task in tasks:
                label=task['family'] if args.action=='build' else task['id']
                state['active']=label;save(state_path,state)
                check_space(args)
                command=container(args,image,name,task['family'],perf=args.action=='run')+[
                    'python3','-B','/control/worker.py','build' if args.action=='build' else 'trial',json.dumps(task)]
                print(f'{args.action}: {label}',flush=True)
                bounded(command,args.work_root/(args.action+'-'+label+'.log'),name,
                        28800,args,deadline)
                state['completed'].append(label);save(state_path,state)
            if args.action=='run':collect_summary(args,plan)
            state.update(status='completed',finished=time.time())
        except BaseException as error:
            state.update(status='failed',error=repr(error));raise
        finally:save(state_path,state)


if __name__=='__main__':main()
