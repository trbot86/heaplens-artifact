"""Save built variants, then run a fixed interleaved or blocked experiment."""
import argparse
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import time

try:
    from . import perfstat_results as metrics
except ImportError:
    import perfstat_results as metrics


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def schedule(names, repetitions, order):
    if order == 'blocked':
        return [(name, rep) for name in names for rep in range(repetitions)]
    sequence = []
    for rep in range(repetitions):
        offset = rep % len(names)
        block = names[offset:] + names[:offset]
        if (rep // len(names)) % 2:
            block.reverse()
        sequence.extend((name, rep) for name in block)
    return sequence


def register(args):
    plan_path = Path(args.plan)
    if (plan_path.parent / 'execution.json').exists():
        raise ValueError('Cannot add variants to an executed campaign')
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
    else:
        plan = {'repetitions': args.reps, 'variants': [], 'counter_scope':
                'Whole-process counters including setup/teardown, divided by measured operations.'}
    if args.reps != plan['repetitions'] or args.reps < 1:
        raise ValueError('Every variant must have the same positive repetition count')
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', args.variant):
        raise ValueError('Invalid variant name')
    if any(v['name'] == args.variant for v in plan['variants']):
        raise ValueError('Variant already registered: ' + args.variant)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    source = str(Path(args.binary).resolve())
    if command.count(source) != 1:
        raise ValueError('Command must contain exactly one absolute benchmark binary')
    # Save before the next make clean can replace this variant.
    binary_dir = plan_path.parent / 'binaries'
    binary_dir.mkdir(exist_ok=True)
    binary = binary_dir / args.variant
    if binary.exists():
        raise ValueError('Refusing to overwrite a saved binary')
    shutil.copy2(source, binary)
    command[command.index(source)] = str(binary.resolve())
    # TPC-C's separately loaded jemalloc needs extra static TLS. Leave ASCYLIB's
    # tuning unchanged, and record the inherited value if one was supplied.
    env = {'GLIBC_TUNABLES': ('glibc.rtld.optional_static_tls=4194304'
                            if args.benchmark == 'tpcc' else os.environ.get('GLIBC_TUNABLES', '')),
           'LD_PRELOAD': args.preload, 'LD_LIBRARY_PATH': args.library_path}
    if args.build_log:
        shutil.copy2(args.build_log, binary_dir / (args.variant + '.build.log'))
    plan['variants'].append({'name': args.variant, 'benchmark': args.benchmark,
        'threads': args.threads, 'cwd': str(Path(args.cwd).resolve()), 'command': command,
        'binary': str(binary.resolve()), 'binary_sha256': digest(binary), 'environment': env,
        'preload_sha256': digest(args.preload) if args.preload else None})
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')


def execute(args):
    plan_path = Path(args.plan)
    plan = json.loads(plan_path.read_text())
    variants = {v['name']: v for v in plan['variants']}
    if not variants:
        raise ValueError('No registered variants')
    runs = schedule(list(variants), plan['repetitions'], args.order)
    run_dir = plan_path.parent
    # Refuse to resume into or truncate any earlier campaign.
    with (run_dir / 'execution.json').open('x') as f:
        json.dump({'order': args.order, 'sequence': runs, 'perf': args.perf,
                   'pause_seconds': args.pause_seconds}, f, indent=2)
    with open(args.results, newline='') as f:
        rows = list(csv.reader(f, delimiter='\t'))
    if rows != [metrics.FIELDS]:
        raise ValueError('Results must contain only the expected header before running')
    for variant in variants.values():
        if digest(variant['binary']) != variant['binary_sha256']:
            raise ValueError('Saved binary changed')
        preload = variant['environment']['LD_PRELOAD']
        if preload and digest(preload) != variant['preload_sha256']:
            raise ValueError('Allocator changed')
    if 'dvy_runtime' in plan:
        try:
            from . import dvy_runtime
        except ImportError:
            import dvy_runtime
        dvy_runtime.diagnose(plan, run_dir)
    for name, repetition in runs:
        v = variants[name]
        stem = '{}.t{}.r{}'.format(name, v['threads'], repetition)
        log_path, perf_path = run_dir / ('stdout.' + stem + '.log'), run_dir / ('perf.' + stem + '.csv')
        env = os.environ.copy()
        for key, value in v['environment'].items():
            if value:
                env[key] = value
            else:
                env.pop(key, None)
        command = v['command']
        if args.perf == 'on':
            command = ['perf', 'stat', '-x,', '-e', args.events, '-o', str(perf_path), '--', *command]
        else:
            perf_path.touch(exist_ok=False)
        with (run_dir / (stem + '.command.json')).open('x') as f:
            json.dump({'command': command, 'benchmark_command': v['command'],
                       'cwd': v['cwd'], 'environment': v['environment'],
                       'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}, f, indent=2)
        with log_path.open('x') as output:
            try:
                subprocess.run(command, cwd=v['cwd'], env=env, stdout=output,
                               stderr=subprocess.STDOUT, check=True)
            except subprocess.CalledProcessError as exc:
                raise RuntimeError('Trial failed; inspect {} and {}'.format(log_path, perf_path)) from exc
        row = metrics.make_row(v['benchmark'], log_path.read_text(), perf_path.read_text(),
                               name, v['threads'], repetition)
        with open(args.results, 'a', newline='') as f:
            csv.DictWriter(f, metrics.FIELDS, delimiter='\t', lineterminator='\n').writerow(row)
        print('  {} repetition {}: {} operations/s'.format(name, repetition, row['throughput_ops_s']), flush=True)
        if args.pause_seconds:
            time.sleep(args.pause_seconds)


def summarize(args):
    dvy_check = Path(args.results).parent / 'runs/dvy-page-checks/summary.json'
    if dvy_check.exists():
        check = json.loads(dvy_check.read_text())
        print('DVY huge-page advice mode={}; page backing: {} (separate diagnostics)'.format(check['mode'], check['status']))
    groups = {}
    with open(args.results) as f:
        for row in csv.DictReader(f, delimiter='\t'):
            groups.setdefault((row['variant'], row['threads']), []).append(float(row['throughput_ops_s']))
    means = {key: statistics.mean(xs) for key, xs in groups.items()}
    for (variant, threads), xs in groups.items():
        sd = '{:.2f}'.format(statistics.stdev(xs)) if len(xs) > 1 else 'NA'
        print('{} threads={} n={} mean={:.2f} ops/s SD={}'.format(variant, threads, len(xs), means[variant, threads], sd))
    for threads in dict.fromkeys(t for _, t in groups):
        names = [v for v, t in groups if t == threads]
        if 'e_single_recmgr_mimalloc_fixed' in names:
            pairs = [('d_single_recmgr', 'a_jemalloc', 'shared reclaimer; jemalloc'),
                     ('e_single_recmgr_mimalloc_fixed', 'b_mimalloc', 'shared reclaimer + row padding; mimalloc'),
                     ('b_mimalloc', 'a_jemalloc', 'global allocator swap'),
                     ('c_mimalloc_fixed', 'b_mimalloc', 'row padding AND removal of segregation')]
        else:
            pairs = [(v, names[0], 'versus baseline') for v in names[1:]]
        for optimized, baseline, label in pairs:
            if (optimized, threads) in means and (baseline, threads) in means:
                gain = 100 * (means[optimized, threads] / means[baseline, threads] - 1)
                print('{} / {}: {:+.2f}% ({}; threads={})'.format(optimized, baseline, gain, label, threads))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    add = sub.add_parser('add')
    for field in ('plan', 'variant', 'binary', 'cwd'):
        add.add_argument('--' + field, required=True)
    add.add_argument('--benchmark', choices=('ascylib', 'tpcc'), required=True)
    add.add_argument('--threads', type=int, required=True)
    add.add_argument('--reps', type=int, required=True)
    add.add_argument('--preload', default='')
    add.add_argument('--library-path', default='')
    add.add_argument('--build-log')
    add.add_argument('command', nargs=argparse.REMAINDER)
    run = sub.add_parser('run')
    run.add_argument('--plan', required=True)
    run.add_argument('--results', required=True)
    run.add_argument('--order', choices=('interleaved', 'blocked'), default='interleaved')
    run.add_argument('--perf', choices=('on', 'off'), default='on')
    run.add_argument('--events', default=','.join(e for e, _ in metrics.EVENTS))
    run.add_argument('--pause-seconds', type=float, default=2)
    summary = sub.add_parser('summary')
    summary.add_argument('--results', required=True)
    args = p.parse_args()
    if args.action == 'run' and args.pause_seconds < 0:
        p.error('pause must be nonnegative')
    {'add': register, 'run': execute, 'summary': summarize}[args.action](args)


if __name__ == '__main__':
    main()
