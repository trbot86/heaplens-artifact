"""Bounded local Docker controller for the temporal cache ablation.

Run under WSL with a private study directory. Source and inputs are snapshotted
before measuring; canonical databases are never writable inside a worker.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while block := f.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def bounded_docker(study, label, arguments, seconds=120, extra_mounts=()):
    name = 'heaplens-ablation-' + label + '-' + str(os.getpid())
    existing = subprocess.run(['docker', 'container', 'inspect', name],
                              capture_output=True, timeout=10)
    if existing.returncode == 0:
        raise RuntimeError(f'Refusing to reuse or remove existing container {name}')
    output = study / 'evidence'
    logpath = output / (label + '.log')
    command = ['docker', 'run', '--name', name, '--network', 'none',
               '--cpus', '2', '--memory', '12g', '--pids-limit', '128',
               '--read-only', '--tmpfs', '/tmp:rw,size=1g',
               '-e', 'OPENBLAS_NUM_THREADS=1', '-e', 'OMP_NUM_THREADS=1',
               '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'MPLCONFIGDIR=/tmp/mpl',
               '-v', f'{study / "candidate"}:/candidate:ro',
               '-v', f'{study / "inputs"}:/inputs:ro',
               '-v', f'{output}:/evidence', *extra_mounts,
               '--entrypoint', 'timeout', 'heaplens-atc26:submission',
               '--signal=TERM', '--kill-after=3s', str(seconds)+'s', *arguments]
    started = time.monotonic()
    watchdog = None
    with logpath.open('x') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                if time.monotonic() - started > seconds + 15:
                    watchdog = 'wall-time-limit'
                    break
                if sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) > 1024**3:
                    watchdog = 'evidence-disk-limit'
                    break
                time.sleep(0.5)
            if watchdog:
                subprocess.run(['docker', 'kill', name], capture_output=True, timeout=10)
            code = process.wait(timeout=15)
        finally:
            state = subprocess.run(['docker', 'inspect', '--format', '{{json .State}}', name],
                                   capture_output=True, text=True, timeout=10)
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=10)
    row = dict(label=label, exit_code=code, watchdog=watchdog,
               wall_seconds=time.monotonic()-started,
               container_state=json.loads(state.stdout) if state.returncode == 0 else None,
               command=command)
    with (output / 'controller.jsonl').open('a') as f:
        f.write(json.dumps(row)+'\n')
    print(json.dumps({k: row[k] for k in ('label','exit_code','watchdog','wall_seconds')}), flush=True)
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workspace', type=Path, required=True)
    ap.add_argument('--study', type=Path, required=True)
    args = ap.parse_args()
    study, workspace = args.study.resolve(), args.workspace.resolve()
    study.mkdir(exist_ok=False)
    (study/'evidence').mkdir()
    (study/'inputs').mkdir()
    source = workspace/'artifact-camera-ready'
    shutil.copytree(source/'sifter_vis_d3/server', study/'candidate/sifter_vis_d3/server',
                    ignore=shutil.ignore_patterns('__pycache__'))
    (study/'candidate/research/camera-ready').mkdir(parents=True)
    script = Path('research/camera-ready/ablate_cache_prefix.py')
    shutil.copy2(source/script, study/'candidate'/script)
    cases = [
        ('valkey', Path('/tmp/heaplens-sampling-gui-20260928-iVVPZe/work/valkey-full/allocs.sqlite'), 4096),
        ('bcco', workspace/'artifact-tools/paper-cluster-audit-20260928/inputs/tpcc-bcco-retained/allocs.sqlite', 2097152),
    ]
    manifest = {'source': {str(p.relative_to(study/'candidate')): digest(p)
                for p in (study/'candidate').rglob('*.py')}, 'inputs': [],
                'image': subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',
                          'heaplens-atc26:submission'], text=True).strip(),
                'environment': subprocess.check_output(['uname','-a'],text=True).strip(),
                'limits': {'cpus':2,'memory_gib':12,'worker_seconds':120,'cache_seconds':30},
                'buckets':2000,'page_budget':128,'record_budget':100000}
    for name, path, page in cases:
        shutil.copy2(path, study/'inputs'/(name+'.sqlite'))
        source_hash = digest(path)
        assert source_hash == digest(study/'inputs'/(name+'.sqlite'))
        manifest['inputs'].append(dict(name=name,source=str(path),sha256=source_hash,
                                       bytes=path.stat().st_size,page_size=page))
    (study/'evidence/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    started = time.monotonic()
    base = ['python3','/candidate/'+str(script),'--root','/candidate']
    assert bounded_docker(study,'self-test',base+['--self-test'],30)['exit_code'] == 0
    results = []
    for name, _, page in cases:
        expected = None
        for rep in (-1,0,1,2):
            policies = ['prefix'] if rep == -1 else (['prefix','direct'] if rep % 2 == 0 else ['direct','prefix'])
            for policy in policies:
                if time.monotonic()-started > 1800:
                    raise TimeoutError('30-minute cache campaign budget reached')
                label = f'{name}-{policy}-{rep}'
                command = base+['--database',f'/inputs/{name}.sqlite','--page-size',str(page),
                    '--buckets','2000','--policy',policy,'--output',f'/evidence/{label}.json']
                outcome = bounded_docker(study,label,command)
                if outcome['exit_code']:
                    raise RuntimeError(f'Stopping at failed/censored pilot {label}; inspect its log.')
                row = json.loads((study/'evidence'/(label+'.json')).read_text())
                if expected is None:
                    expected = row['payload_sha256']
                assert row['payload_sha256'] == expected, f'Complete payload mismatch: {label}'
                row.update(case=name,rep=rep)
                results.append(row)
                (study/'evidence/results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps({'complete':True,'trials_including_warmup':len(results),
                      'all_paired_payloads_equal':True}),flush=True)


if __name__ == '__main__':
    main()
