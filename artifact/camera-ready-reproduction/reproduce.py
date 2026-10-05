#!/usr/bin/env python3
"""Portable frozen-source CR studies. Default: plan only; never starts a workload."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request
import uuid
import metrics

BUNDLE = Path(__file__).resolve().parent
IMAGE = 'heaplens-atc26:submission'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while block:=f.read(1024*1024): h.update(block)
    return h.hexdigest()


def write(path, data):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(data,f,indent=2);f.write('\n')


def verify(bundle=BUNDLE):
    manifest=metrics.read(bundle/'manifest.json')
    for name,entry in manifest['assets'].items():
        if (bundle/name).stat().st_size!=entry['bytes'] or digest(bundle/name)!=entry['sha256']:
            raise ValueError('Asset integrity failure: '+name)
    for name,entry in manifest['saved'].items():
        if digest(bundle/'saved'/name)!=entry['sha256']:
            raise ValueError('Saved evidence changed: '+name)
    return manifest


def extract(archive, destination, expected):
    with tarfile.open(archive) as tar:
        seen=set()
        for member in tar:
            name=member.name;relative=PurePosixPath(name)
            if not member.isfile() or relative.is_absolute() or '..' in relative.parts or '\\' in name or name in seen or name not in expected:
                raise ValueError('Unsafe or unexpected archive member: '+name)
            data=tar.extractfile(member).read();entry=expected[name]
            if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:
                raise ValueError('Extracted content mismatch: '+name)
            target=destination/name
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f: f.write(data)
            target.chmod(member.mode)
            seen.add(name)
        if seen!=set(expected): raise ValueError('Missing archive members')


def prepare(out, bundle=BUNDLE):
    manifest=verify(bundle)
    out.mkdir(parents=True,exist_ok=False)
    for name,entry in manifest['assets'].items(): extract(bundle/name,out,entry['files'])
    (out/'evidence').mkdir();(out/'work').mkdir()
    write(out/'inputs.json',dict(manifest_sha256=digest(bundle/'manifest.json'),
          platform=platform.platform(),python=sys.version,scope=manifest['scope']))
    return out


def bounded(command, log, seconds, env=None):
    """Keep failed logs and terminate only the process tree we start."""
    with Path(log).open('x') as stream:
        options=dict(stdout=stream,stderr=subprocess.STDOUT,env=env)
        if os.name=='nt': options['creationflags']=subprocess.CREATE_NEW_PROCESS_GROUP
        else: options['start_new_session']=True
        process=subprocess.Popen(list(map(str,command)),**options)
        try: code=process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            if os.name=='nt': subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
            else:
                os.killpg(process.pid,signal.SIGTERM)
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: os.killpg(process.pid,signal.SIGKILL)
            process.wait(timeout=15)
            raise TimeoutError('Stopped bounded command; see '+str(log))
    if code: raise RuntimeError('Command failed; see '+str(log))


class Docker:
    def __init__(self,out,image):
        self.out=out;self.owned=[]
        self.image=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',image],text=True,timeout=20).strip()
        write(out/'image.json',dict(requested=image,id=self.image))

    def command(self,label,mounts,command,seconds,cpus=2,memory=12,ports=(),env=None,workdir=None,background=False):
        name='heaplens-cr-reproduce-'+uuid.uuid4().hex[:16]
        self.owned.append(name)
        cmd=['docker','run','--name',name,'--init','--network','bridge' if ports else 'none',
             '--cpus',str(cpus),'--memory',str(memory)+'g','--pids-limit','512',
             '-e','OPENBLAS_NUM_THREADS=1','-e','OMP_NUM_THREADS=1','-e','PYTHONDONTWRITEBYTECODE=1',
             '-e','NEXT_TELEMETRY_DISABLED=1']
        if background: cmd+=['-d']
        for path,target,mode in mounts: cmd+=['-v',str(Path(path).resolve())+':'+target+':'+mode]
        for port,target in ports: cmd+=['-p',f'127.0.0.1:{port}:{target}']
        for key,value in (env or {}).items():cmd+=['-e',key+'='+str(value)]
        if workdir:cmd+=['-w',workdir]
        cmd+=['--entrypoint','timeout',self.image,'--signal=TERM','--kill-after=10s',str(seconds)+'s',*command]
        write(self.out/'evidence'/(label+'-command.json'),cmd)
        bounded(cmd,self.out/'evidence'/(label+'.log'),30 if background else seconds+30)
        return name

    def close(self):
        errors=[]
        for i,name in enumerate(self.owned):
            try:
                with (self.out/'evidence'/f'container-{i}-final.log').open('x') as stream:
                    subprocess.run(['docker','logs',name],stdout=stream,stderr=subprocess.STDOUT,timeout=20)
            except (OSError,subprocess.TimeoutExpired) as exc:errors.append(str(exc))
            try:
                result=subprocess.run(['docker','rm','-f',name],capture_output=True,text=True,timeout=30)
                if result.returncode:errors.append(name+': '+result.stderr)
            except (OSError,subprocess.TimeoutExpired) as exc:errors.append(name+': '+str(exc))
        self.owned.clear()
        write(self.out/'cleanup.json',dict(status='failed' if errors else 'passed',errors=errors))
        if errors:raise RuntimeError('Container cleanup incomplete; see '+str(self.out/'cleanup.json'))


def backend(docker,out,check=False):
    mounts=[(out/'sources/backend','/candidate','ro'),(out/'inputs/backend','/inputs','ro'),(out/'evidence','/evidence','rw')]
    base=['python3','-B','/candidate/tools/ablate_backend_matrix.py','--root','/candidate']
    docker.command('backend-self-test',mounts,base+['--self-test'],60)
    if check:return dict(status='passed',scope='Synthetic backend equality checks; no measured input')
    rows=[];start=time.monotonic();cells=[('enumerated','direct'),('enumerated','prefix'),('range','prefix'),('range','direct')]
    for case,page in [('valkey',4096),('bcco',2097152)]:
        expected=None
        for rep in (-1,0,1,2):
            shift=max(rep,0)
            for spatial,policy in cells[shift:]+cells[:shift]:
                if time.monotonic()-start>1800:raise TimeoutError('Backend campaign limit reached')
                label=f'{case}-{spatial}-{policy}-{rep}'
                docker.command(label,mounts,base+['--database',f'/inputs/{case}.sqlite','--page-size',str(page),
                    '--spatial',spatial,'--policy',policy,'--output',f'/evidence/{label}.json'],180)
                row=metrics.read(out/'evidence'/(label+'.json'))
                if expected is not None and row['payload_sha256']!=expected:raise ValueError('Complete output differs across backend cells')
                expected=row['payload_sha256'];row.update(case=case,rep=rep);rows.append(row)
                write(out/'evidence'/(label+'-row.json'),row)
    write(out/'evidence/results.json',rows)
    return metrics.backend(rows)


def sampling(docker,out):
    mounts=[(out/'sources/sampling/source','/root/sifter','ro'),(out/'sources/sampling/tools','/author-tools','ro'),
            (out/'inputs/retained','/retained','ro'),(out/'evidence','/evidence','rw'),(out/'work','/work','rw')]
    docker.command('sampling',mounts,['python3','-B','-u','/author-tools/run_final_sampling.py'],10800,
                   cpus=4,env={'CR_REVISION':'7f4f5f20125ad0a2571abc8ddb0e98e13c7ae109'})
    return metrics.sampling(metrics.read(out/'evidence/all-results.json'),
                            [metrics.read(out/'evidence'/f'efrb-r{r:02d}/result.json') for r in range(20)])


def check(docker,out):
    backend(docker,out,check=True)
    control=out/'sources/ui/tools'
    # Compile the exact converter inputs without processing a retained trace.
    build="from pathlib import Path;import subprocess;subprocess.run(['g++','-std=c++17','-O1',*map(str,sorted(Path('/root/sifter/type_analysis/convert_to_db').glob('*.cpp'))),'-lsqlite3','-lpthread','-ltbb','-o','/work/convert'],check=True)"
    docker.command('converter-compile',[(out/'sources/sampling/source','/root/sifter','ro'),(out/'work','/work','rw')],
        ['python3','-c',build],180,cpus=4,memory=4)
    for name in ('benchmark_optimization_browser.cjs','benchmark_large_ui.cjs','optimization_ui_probe.js'):
        docker.command(name+'-syntax',[(control,'/control','ro')],['node','--check','/control/'+name],20,memory=1)
    fixtures=out/'work/fixtures';fixtures.mkdir()
    docker.command('fixture-check',[(control,'/control','ro'),(out/'inputs/ui','/author-tools','ro'),(fixtures,'/fixtures','rw')],
        ['python3','/control/serve_large_ui_fixtures.py','--prepare','--only','dense64k'],60,memory=4)
    payload=metrics.read(fixtures/'dense64k.json')
    pages=payload['pagesData']['page_num_events']
    if len(pages)!=1 or sum(len(p['events']) for p in pages.values())!=65536:
        raise ValueError('Synthetic fixture has wrong shape')
    return dict(status='passed',scope='Backend synthetic equality, native converter compile, browser-harness syntax, synthetic fixture structure; no measured trials or browser latency run')


def available_ports(ports):
    for port in ports:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',port))


def ready(url,seconds=120):
    start=time.monotonic()
    while time.monotonic()-start<seconds:
        try:
            with urllib.request.urlopen(url,timeout=2) as response:
                if response.status==200:return
        except OSError:time.sleep(.3)
    raise TimeoutError('Server did not become ready: '+url)


def ui(docker,out,args):
    case=args.command.removeprefix('ui-');ports=[3000,3001] if case=='toggle' else [3002,3003]
    available_ports([5000,*ports])
    control=out/'sources/ui/tools';fixtures=out/'work/fixtures'
    fixtures.mkdir()
    if case=='detail':
        docker.command('prepare-fixtures',[(control,'/control','ro'),(out/'inputs/ui','/author-tools','ro'),(fixtures,'/fixtures','rw')],
            ['python3','/control/serve_large_ui_fixtures.py','--prepare'],180,memory=4)
        server=['python3','/control/serve_large_ui_fixtures.py']
    else:server=['python3','/control/optimization_ui_server.py']
    docker.command('replay-server',[(control,'/control','ro'),(out/'inputs/ui','/author-tools','ro'),(fixtures,'/fixtures','ro')],
        server,2400,memory=4,ports=[(5000,5000)],background=True)
    for policy,port in zip(('baseline','optimized'),ports):
        source=out/'sources/ui'/(case+'-'+policy)
        docker.command('frontend-'+policy,[(source,'/ui','rw')],
            ['bash','-lc','ln -s /opt/heaplens-ui/node_modules /ui/node_modules && exec npm run dev -- --hostname 0.0.0.0'],
            2400,cpus=4,memory=8,ports=[(port,3000)],workdir='/ui',background=True)
        ready(f'http://127.0.0.1:{port}')
    env=dict({k:v for k,v in os.environ.items() if not k.startswith('HEAPLENS_')},HEAPLENS_PLAYWRIGHT=str(Path(args.playwright).resolve()),HEAPLENS_BROWSER=str(Path(args.browser).resolve()),
             HEAPLENS_EVIDENCE=str(out/'evidence'))
    write(out/'browser.json',dict(browser=args.browser,node=args.node,playwright=args.playwright,
        playwright_version=metrics.read(Path(args.playwright)/'package.json')['version'],
        node_version=subprocess.check_output([args.node,'--version'],text=True,timeout=10).strip(),
        environment_note=args.environment_note,scope='Host browser; report GPU acceleration and display environment separately'))
    if case=='toggle':
        bounded([args.node,control/'benchmark_optimization_browser.cjs'],out/'evidence/browser-controller.log',1800,env)
        return metrics.toggle(metrics.jsonlines(out/'evidence/browser.jsonl'))
    deadline=time.monotonic()+1800
    def trial(policy,name,rep):
        if time.monotonic()>deadline:raise TimeoutError('Detail campaign limit reached')
        folder=out/'evidence'/('warmup-'+policy if rep<0 else policy);folder.mkdir(exist_ok=True)
        settings=dict(env,HEAPLENS_EVIDENCE=str(folder),HEAPLENS_UI_PORT='3002' if policy=='baseline' else '3003',
            HEAPLENS_CASES=json.dumps([name]),HEAPLENS_REPS='1',HEAPLENS_REP_OFFSET=str(rep),HEAPLENS_WARMUP='0',
            HEAPLENS_JS_HEAP_MB='default',HEAPLENS_EXACT_REGION_BYTES='65536',
            HEAPLENS_EXPECT_DETAIL_RECTS='' if rep<0 else str(2050 if policy=='optimized' else 7815 if name=='live1m' else 65538))
        bounded([args.node,control/'benchmark_large_ui.cjs'],out/'evidence'/f'{policy}-{name}-{rep}-controller.log',210,settings)
        rows=metrics.jsonlines(folder/'browser.jsonl');last=[r for r in rows if r.get('checkpoint')=='final'][-1]
        if last['status']!='complete' or last['errors']:raise ValueError('Detail browser trial failed')
    for policy in ('baseline','optimized'):trial(policy,'live100k',-1)
    for rep in range(3):
        for name in ('dense64k','dense1m','live1m'):
            for policy in (('optimized','baseline') if rep%2 else ('baseline','optimized')):trial(policy,name,rep)
    return metrics.detail(metrics.jsonlines(out/'evidence/baseline/browser.jsonl'),metrics.jsonlines(out/'evidence/optimized/browser.jsonl'))


def parse_args(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',nargs='?',default='plan',choices=['plan','verify','prepare','check','backend','sampling','ui-toggle','ui-detail'])
    p.add_argument('--out',type=Path,help='New, non-existing output directory')
    p.add_argument('--image',default=IMAGE)
    p.add_argument('--acknowledge-cost',action='store_true')
    p.add_argument('--browser',help='Host Edge/Chromium executable; no automatic download')
    p.add_argument('--playwright',help='Absolute path to installed host playwright package directory')
    p.add_argument('--node',default='node')
    p.add_argument('--environment-note',default='',help='Record host GPU/compositor conditions')
    args=p.parse_args(argv)
    if args.command not in {'plan','verify'} and args.out is None:p.error('--out is required')
    if args.command in {'backend','sampling','ui-toggle','ui-detail'} and not args.acknowledge_cost:p.error('--acknowledge-cost is required')
    if args.command.startswith('ui-') and not(args.browser and args.playwright):p.error('--browser and --playwright are required')
    if args.command.startswith('ui-'):
        if not Path(args.browser).is_file() or not (Path(args.playwright)/'package.json').is_file():
            p.error('Supply an existing browser executable and playwright package directory')
    return args


def main(argv=None):
    args=parse_args(argv)
    if args.command=='plan':
        print(json.dumps(dict(backend='32 runs: 8 warmups + 24 measured',sampling='100 Valkey + 20 EFRB selections',
            ui_toggle='18 browser contexts plus warmup',ui_detail='18 fresh-browser trials plus 2 warmups',
            scope='Frozen source/input reproduction; no workload is launched by plan or verify'),indent=2));return
    if args.command=='verify':
        verify();print(json.dumps(metrics.saved(BUNDLE/'saved'),indent=2));return
    out=args.out.resolve()
    ancestor=out.parent
    while not ancestor.exists():ancestor=ancestor.parent
    needed=16 if args.command=='sampling' else 4
    if shutil.disk_usage(ancestor).free < needed*1024**3:raise ValueError(f'Need {needed} GiB free for fresh study outputs')
    prepare(out)
    if args.command=='prepare':print(out);return
    docker=None
    try:
        docker=Docker(out,args.image)
        if args.command=='backend':result=backend(docker,out)
        elif args.command=='check':result=check(docker,out)
        elif args.command=='sampling':result=sampling(docker,out)
        else:result=ui(docker,out,args)
        write(out/'summary.json',dict(status='passed',study=args.command,result=result))
        print('Results:',out)
    except Exception as exc:
        write(out/'failure.json',dict(error=str(exc),study=args.command));raise
    finally:
        if docker is not None:docker.close()


if __name__=='__main__':main()
