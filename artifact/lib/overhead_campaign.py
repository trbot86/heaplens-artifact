"""Portable baseline-versus-logging reproduction of the C2 overhead experiment."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import time

TREES = {'efrb': ('bst-ellen', 'lf-bst_ellen'),
         'dvy': ('bst-drachsler', 'lb-bst-drachsler'),
         'bcco': ('bst-bronson', 'lb-bst_bronson')}


def archive_trace(raw, destination):
    """Compress, independently verify, then remove only the new raw trial log."""
    if not raw.is_file() or raw.stat().st_size == 0 or raw.stat().st_size % 40:
        raise RuntimeError(f'Missing, empty, or truncated 40-byte event log: {raw}')
    size = raw.stat().st_size
    digest = hashlib.sha256()
    allocations = frees = 0
    with raw.open('rb') as src, gzip.open(destination, 'xb', compresslevel=1) as dst:
        for chunk in iter(lambda: src.read(40*65536), b''):
            kinds = chunk[36::40]
            allocations += kinds.count(1)
            frees += kinds.count(0)
            if kinds.count(1)+kinds.count(0) != len(kinds):
                raise RuntimeError('Invalid event kind; raw log preserved')
            digest.update(chunk)
            dst.write(chunk)
    if not allocations or not frees:
        raise RuntimeError('Expected both allocation and free events; raw log preserved')
    check = hashlib.sha256()
    with gzip.open(destination, 'rb') as src:
        for chunk in iter(lambda: src.read(1024*1024), b''):
            check.update(chunk)
    if check.digest() != digest.digest():
        raise RuntimeError('Compressed trace verification failed; raw log preserved')
    raw.unlink()
    return dict(bytes=size, records=size//40, allocations=allocations, frees=frees,
                sha256=digest.hexdigest())


def execute(args, out, api):
    import fcntl
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', str(out)):
        raise ValueError('Overhead builds require an output path without spaces or shell metacharacters')
    paper = args.profile == 'paper'
    trees = args.overhead_trees or list(TREES)
    threads = args.threads or (24 if paper else min(2, len(os.sched_getaffinity(0))))
    initial = args.initial or (10000000 if paper else 4096)
    duration = args.duration_ms or (3000 if paper else 1000)
    reps = args.reps or (10 if paper else 1)
    updates = [args.update_pct] if args.update_pct is not None else [20, 100]
    placement = []
    if paper or args.cpus or args.memory_policy:
        cpus = api.node_cpus(args.server_node, threads, args.cpus)
        placement = ['numactl', '--physcpubind='+','.join(map(str, cpus)),
                     '--'+(args.memory_policy or 'interleave')+'='+str(args.server_node)]
    plan = dict(trees=trees, threads=threads, initial_requested=initial,
                initial_rounded=1 << (initial-1).bit_length(), duration_ms=duration,
                repetitions=reps, updates=updates, placement=placement,
                scope='Uninstrumented baseline versus instrumented stock logger; no wait probe')
    api.save(out/'protocol.json', plan)
    env = dict(os.environ, HEAPLENS_ROOT=str(api.ROOT), HEAPLENS_OVERHEAD_DIR=str(out),
               JOBS=str(args.jobs), OVERHEAD_TREES=' '.join(trees))
    # sifter.sh also builds shared instrumentation tools; do not race named traces.
    with (api.ART/'.experiment.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        api.run(['bash', api.ART/'lib/overhead_build.sh'], env=env,
                log=out/'build.log', timeout=7200)
    build = out/'build'
    rows = []
    for tree in trees:
        subdir, binary_name = TREES[tree]
        for update in updates:
            for rep in range(reps):
                for arm in (['baseline','logging'] if rep%2==0 else ['logging','baseline']):
                    if shutil.disk_usage(out).free < (50 if paper else 2)*1024**3:
                        raise RuntimeError('Insufficient free trace storage; completed runs preserved')
                    trial = out/f'{tree}-u{update}-{arm}-{rep:02d}'
                    trial.mkdir()
                    binary = build/f'{tree}-{arm}'/'bin'/binary_name
                    preload = str(build/'ssmem/libssmem_x86_64.so')
                    raw = trial/'events.bin'
                    if arm == 'logging':
                        preload = str(build/'stock-memhook/libmemhook.so')+':'+preload
                    assignments = ['LD_LIBRARY_PATH='+str(build/'ssmem'), 'LD_PRELOAD='+preload]
                    if arm == 'logging': assignments += ['MEMHOOK_OUTPUT_DUMP_FILE='+str(raw)]
                    command = placement+['env', *assignments, str(binary), '-i', str(initial),
                                         '-n', str(threads), '-u', str(update), '-d', str(duration)]
                    record = dict(tree=tree, update=update, arm=arm, rep=rep, command=command,
                        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
                    api.save(trial/'command.json', record)
                    clean = dict(os.environ)
                    for key in ('LD_PRELOAD','LD_LIBRARY_PATH','MALLOC_CONF','GLIBC_TUNABLES'):
                        clean.pop(key, None)
                    print(f'Overhead: {tree}, {update}% updates, {arm}, repetition {rep+1}', flush=True)
                    started = time.monotonic()
                    file_limit = (20 if paper else 1)*1024**3
                    api.run(['timeout','--kill-after=10s','900s','prlimit',
                             f'--fsize={file_limit}:{file_limit}', '--', *command],
                            cwd=build/f'{tree}-{arm}'/'src'/subdir,
                            env=clean, log=trial/'benchmark.log', timeout=920)
                    record['wall_seconds'] = time.monotonic()-started
                    text = (trial/'benchmark.log').read_text()
                    if re.search(r'aio_write FAILED|aio_suspend failed|Error in `dlsym`', text):
                        raise RuntimeError(f'Logger error in {trial}')
                    matches = re.findall(r'#txs\s+\d+\s+\(\s*([\d.]+)', text)
                    if len(matches)!=1: raise RuntimeError(f'Missing throughput in {trial}')
                    record['ops_per_second'] = float(matches[0])
                    if arm=='logging':
                        record['trace'] = archive_trace(raw, trial/'events.bin.gz')
                        for filename in ('typeset_dump.txt','fileset_dump.txt','fielddump.txt'):
                            src = build/f'{tree}-{arm}'/'src'/subdir/filename
                            if src.exists(): shutil.copy2(src, trial/filename)
                    api.save(trial/'result.json', record)
                    rows.append(record)
                    api.save(out/'results.json', rows)
    summary=[]
    for tree in trees:
        for update in updates:
            values={a:[r['ops_per_second'] for r in rows if r['tree']==tree and
                       r['update']==update and r['arm']==a] for a in ('baseline','logging')}
            base, logged = (statistics.mean(values[a]) for a in ('baseline','logging'))
            summary.append(dict(tree=tree,update_pct=update,runs_per_arm=reps,
                baseline_ops_per_second=base,logging_ops_per_second=logged,
                throughput_reduction_pct=100*(1-logged/base),raw=values))
    api.save(out/'summary.json',summary)
    print(json.dumps(summary,indent=2))
