"""DVY-only runtime selection and separate page-backing diagnostics."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

BUNDLE = Path('/opt/heaplens-dvy-runtime')
LIBRARIES = ('ld-linux-x86-64.so.2', 'libc.so.6', 'libpthread.so.0',
             'libm.so.6', 'libdl.so.2', 'librt.so.1', 'libgcc_s.so.1')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean_environment():
    env = os.environ.copy()
    for key in ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'GLIBC_TUNABLES'):
        env.pop(key, None)
    return env


def policies():
    root = Path('/sys/kernel/mm/transparent_hugepage')
    result = {}
    for name in ('enabled', 'defrag', 'hpage_pmd_size'):
        try:
            result[name] = (root / name).read_text().strip()
        except OSError:
            result[name] = None
    return result


def configure(path, mode='auto', profile='smoke', bundle=BUNDLE):
    path = Path(path)
    plan = json.loads(path.read_text())
    if (path.parent / 'execution.json').exists() or 'dvy_runtime' in plan:
        raise ValueError('Refusing to reconfigure an existing DVY campaign')
    expected = {'a_96B_default', 'b_72B_no_pad', 'c_128B_pad', 'd_192B_pad'}
    if {v['name'] for v in plan['variants']} != expected or mode not in {'auto', 'require', 'off'}:
        raise ValueError('DVY runtime configuration requires all four DVY layouts')
    if any(v['benchmark'] != 'ascylib' or v['environment']['LD_PRELOAD'] for v in plan['variants']):
        raise ValueError('DVY requires ASCYLIB with glibc backing, not an allocator preload')
    warning = None
    loader = bundle / 'ld-linux-x86-64.so.2'
    usable = all((bundle / name).is_file() for name in LIBRARIES)
    listings = {}
    if usable:
        # Verify the complete bundle can load every saved binary before selecting
        # it once for the whole campaign. Never fall back on a per-layout basis.
        try:
            version = subprocess.check_output([str(loader), '--version'], text=True,
                                              env=clean_environment(), stderr=subprocess.STDOUT, timeout=10)
            for v in plan['variants']:
                listings[v['name']] = subprocess.check_output(
                    [str(loader), '--inhibit-cache', '--library-path', str(bundle), '--list', v['binary']],
                    text=True, env=clean_environment(), stderr=subprocess.STDOUT, timeout=10)
                if 'not found' in listings[v['name']]:
                    raise RuntimeError('Unresolved DVY library dependency')
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            usable = False
            warning = 'Bundled DVY runtime cannot load these binaries: ' + str(exc)
    else:
        warning = 'Bundled DVY runtime is missing (older image or native run).'
    if not usable:
        warning += ' Using the installed runtime for all four layouts; rebuild with bash artifact/run.sh build for the supplied corrected libc.'
        print('WARNING: ' + warning, file=sys.stderr)
        version = os.confstr('CS_GNU_LIBC_VERSION') if hasattr(os, 'confstr') else 'unknown'
    tunable = 'glibc.malloc.hugetlb=' + ('0' if mode == 'off' else '1')
    for v in plan['variants']:
        command = v['command']
        index = command.index(v['binary'])
        prefix = ['/usr/bin/env', 'GLIBC_TUNABLES=' + tunable]
        if usable:
            prefix += [str(loader), '--inhibit-cache', '--library-path', str(bundle)]
        v['command'] = command[:index] + prefix + command[index:]
        # The tunable applies only to the benchmark, not Python, perf or numactl.
        v['environment'] = {'LD_PRELOAD': '', 'LD_LIBRARY_PATH': '', 'GLIBC_TUNABLES': ''}
    plan['dvy_runtime'] = dict(mode=mode, profile=profile, bundled=usable,
        version=version, warning=warning, tunable=tunable, policies=policies(),
        libraries={str(bundle / n): sha(bundle / n) for n in LIBRARIES} if usable else {},
        library_listings=listings if usable else {},
        packages=(bundle / 'packages.txt').read_text() if usable and (bundle / 'packages.txt').is_file() else None)
    path.write_text(json.dumps(plan, indent=2) + '\n')


def mapping_values(smaps):
    values = {name: sum(map(int, re.findall(r'^' + name + r':\s*(\d+)', smaps, re.M)))
              for name in ('AnonHugePages', 'Anonymous', 'Rss')}
    values['huge_advised_mappings'] = sum('hg' in line.split()
        for line in re.findall(r'^VmFlags:(.*)$', smaps, re.M))
    return values


def diagnose(plan, run_dir):
    """One untimed full-workload process per layout, then fresh timing processes.

    Unavailable backing/proc access warns in auto mode, never silently claiming
    reproduction. Actual benchmark crashes/timeouts are errors, not fallbacks.
    """
    info = plan['dvy_runtime']
    for name, expected in info['libraries'].items():
        if sha(name) != expected:
            raise RuntimeError('DVY runtime changed after configuration: ' + name)
    root = Path(run_dir) / 'dvy-page-checks'
    root.mkdir()
    report = dict(mode=info['mode'], scope='Separate diagnostic processes; timing processes are unprobed.',
                  policies_before=policies(), rows=[])
    if info['profile'] == 'smoke' and info['mode'] != 'require':
        report['status'] = 'not_checked_small_smoke_workload'
    else:
        for v in plan['variants']:
            directory = root / v['name']; directory.mkdir()
            command = v['command']
            duration = int(command[command.index('-d') + 1]) / 1000
            delay = min(3.0, max(0.05, duration * 0.5))
            (directory / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
            row = dict(variant=v['name'], command=command, sampled_after_seconds=None, error=None)
            start = time.monotonic()
            with (directory / 'stdout.log').open('x') as log:
                proc = subprocess.Popen(command, cwd=v['cwd'], env=clean_environment(),
                                        stdout=log, stderr=subprocess.STDOUT)
                try:
                    time.sleep(delay)
                    try:
                        smaps = Path(f'/proc/{proc.pid}/smaps').read_text()
                        (directory / 'smaps').write_text(smaps)
                        row.update(mapping_values(smaps))
                        row['sampled_after_seconds'] = time.monotonic() - start
                    except OSError as exc:
                        row['error'] = str(exc)
                    code = proc.wait(timeout=max(120, duration + 60))
                    if code:
                        raise RuntimeError(f'DVY diagnostic exited {code}; see {directory}/stdout.log')
                finally:
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill(); proc.wait()
            row['huge_backing_observed'] = row.get('AnonHugePages', 0) > 0
            report['rows'].append(row)
        report['status'] = ('huge_backing_observed_all_layouts' if all(r['huge_backing_observed'] for r in report['rows'])
                            else 'huge_backing_not_confirmed_all_layouts')
    report['policies_after'] = policies()
    (root / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print('DVY page check: ' + report['status'], flush=True)
    if info['mode'] != 'off' and report['status'] == 'huge_backing_not_confirmed_all_layouts':
        message = ('DVY huge-page backing was not confirmed for every layout. Results remain usable, '
                   'but may not reproduce the reported gain. See dvy-page-checks/summary.json; '
                   'the artifact does not change host THP settings.')
        if info['mode'] == 'require':
            raise RuntimeError(message + ' Strict mode stopped before timing.')
        print('WARNING: ' + message, file=sys.stderr)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--mode', choices=['auto', 'require', 'off'], default='auto')
    parser.add_argument('--profile', choices=['smoke', 'paper'], default='smoke')
    args = parser.parse_args()
    configure(args.plan, args.mode, args.profile)
