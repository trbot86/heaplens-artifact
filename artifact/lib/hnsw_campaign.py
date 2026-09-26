"""Saved-module HNSW campaigns with explicit workload and physical placement."""
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def runtime_environment():
    env = os.environ.copy()
    for key in ('LD_PRELOAD', 'PYTHONPATH', 'HNSWLIB_NO_NATIVE',
                'HNSWLIB_BENCH_CXX_DEFINES', 'GLIBC_TUNABLES'):
        env.pop(key, None)
    env.update(PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4')
    return env


def dimensions(args):
    if args.dim is not None:
        return [args.dim]
    if args.command == 'hnsw':
        return [128, 1536] if args.profile == 'paper' else [128]
    return [768 if args.profile == 'paper' or args.command == 'hnsw-factorization' else 128]


def configuration(args, api, dim=None):
    paper = args.profile == 'paper'
    dim = dimensions(args)[0] if dim is None else dim
    threads = args.threads or (24 if paper else 2)
    cpus = api.node_cpus(args.server_node, threads, args.cpus) if paper or args.cpus or args.memory_policy else None
    return dict(dim=dim, threads=threads, build_threads=threads,
                elements=1000000 if paper else (10000 if args.command=='hnsw' else 2000),
                queries=100000 if paper else (1000 if args.command=='hnsw' else 200), m=16, ef_construction=200,
                ef=64, k=10, warmup=10000 if paper else 100,
                iterations=5 if paper else 1, seed=1, query_mode='indexed',
                cpus=cpus, node=args.server_node, memory_policy=api.memory_option(args))


def command(config, label, defines, block):
    cmd = [sys.executable, '-u', 'benchmark.py', '--probe',
           '--variant-label=' + label, '--variant-defines=' + defines,
           '--dims', str(config['dim']), '--repetition', str(block)]
    for key in ('threads', 'build_threads', 'elements', 'queries', 'm', 'ef_construction',
                'ef', 'k', 'warmup', 'iterations', 'seed', 'query_mode'):
        cmd += ['--' + key.replace('_', '-'), str(config[key])]
    if config['cpus'] is not None:
        cmd = ['numactl', '--physcpubind=' + ','.join(map(str, config['cpus'])),
               '--' + config['memory_policy'] + '=' + str(config['node'])] + cmd
    return cmd


def read_result(log, config, label, defines, block):
    row = json.loads(Path(log).read_text().splitlines()[-1])
    expected = {key:config[key] for key in ('dim', 'threads', 'build_threads', 'elements',
        'queries', 'm', 'ef_construction', 'ef', 'k', 'warmup', 'iterations', 'query_mode')}
    expected.update(variant=label, defines=defines, repetition=block,
                    timed_queries=config['queries']*config['iterations'], deleted=0)
    for key, value in expected.items():
        if row.get(key) != value:
            raise ValueError(f'HNSW result mismatch for {key}: {row.get(key)!r} != {value!r}')
    if not math.isfinite(row['qps_mean']) or row['qps_mean'] <= 0:
        raise ValueError('HNSW throughput must be positive and finite')
    if not math.isclose(row['qps_mean']*row['query_seconds'], row['timed_queries'], abs_tol=0.01):
        raise ValueError('HNSW throughput denominator mismatch')
    return row


def dimensional_execution(execution, dims, blocked=False):
    if blocked:
        return [(dim, label, block) for dim in dims for label, block in execution]
    # Each block contains every dimension/variant pair. Reverse dimension order
    # on even blocks, just as in the two-dimension confirmation experiment.
    return [(dim, label, block) for block in dict.fromkeys(b for _, b in execution)
            for dim in (dims if block % 2 else dims[::-1])
            for label, b in execution if b == block]


def execute(args, out, source, cells, execution, api):
    dims = dimensions(args)
    configs = {dim:configuration(args, api, dim) for dim in dims}
    trials = dimensional_execution(execution, dims, args.trial_order == 'blocked')
    env = runtime_environment()
    sources = {str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*'))
               if p.is_file() and not any(x in {'.git', 'build', '__pycache__'} for x in p.relative_to(source).parts)
               and p.suffix not in {'.so', '.o', '.pyc'}}
    api.save(out/'source-manifest.json', sources)
    settings = {key:env.get(key) for key in ('LD_PRELOAD', 'PYTHONPATH', 'GLIBC_TUNABLES',
                'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'PYTHONDONTWRITEBYTECODE')}
    policies = {key:Path(path).read_text() if Path(path).exists() else None for key,path in (
        ('thp','/sys/kernel/mm/transparent_hugepage/enabled'),
        ('defrag','/sys/kernel/mm/transparent_hugepage/defrag'))}
    protocol = {'source':str(source), 'cells':cells,
        'execution':execution, 'runtime_environment':settings, 'policies':policies,
        'dimensions':dims, 'trial_sequence':[dict(dim=d, variant=v, block=b) for d,v,b in trials],
        'allocator':'system libc, LD_PRELOAD unset',
        'quality_metric':'Indexed self-label hit fraction; not ground-truth top-k ANN recall.'}
    if len(dims) == 1:
        protocol['configuration'] = configs[dims[0]]
    else:
        protocol['configurations'] = {str(dim):config for dim,config in configs.items()}
    api.save(out/'protocol.json', protocol)
    binaries = {}
    for label,defines in cells.items():
        work = out/label
        shutil.copytree(source,work,ignore=api.IGNORE)
        build_env = dict(env,HNSWLIB_BENCH_CXX_DEFINES=defines)
        api.run([sys.executable,'setup.py','build_ext','--inplace','--force'],cwd=work,
                log=out/(label+'-build.log'),env=build_env)
        modules = list(work.glob('hnswlib*.so'))
        if len(modules)!=1:raise RuntimeError(f'Expected one built module for {label}')
        binaries[label]={'path':str(modules[0]),'sha256':sha(modules[0]),'defines':defines}
    api.save(out/'binaries.json',binaries)
    values={dim:{label:[] for label in cells} for dim in dims}
    for dim,label,block in trials:
        config=configs[dim]
        binary=binaries[label]
        if sha(binary['path'])!=binary['sha256']:raise RuntimeError('HNSW module changed during campaign')
        stem=f'block{block:02d}_'+(f'd{dim}_' if len(dims)>1 else '')+label
        cmd=command(config,label,cells[label],block)
        api.save(out/(stem+'-command.json'),{'command':cmd,'cwd':str(out/label),'environment':settings,
                 'started_utc':datetime.now(timezone.utc).isoformat()})
        api.run(cmd,cwd=out/label,log=out/(stem+'.log'),env=env)
        if sha(binary['path'])!=binary['sha256']:raise RuntimeError('HNSW module changed during trial')
        row=read_result(out/(stem+'.log'),config,label,cells[label],block)
        with (out/(stem+'.csv')).open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=sorted(row));writer.writeheader();writer.writerow(row)
        values[dim][label].append(row['qps_mean'])
        if args.profile=='paper':time.sleep(15)
    return values if len(dims)>1 else values[dims[0]]
