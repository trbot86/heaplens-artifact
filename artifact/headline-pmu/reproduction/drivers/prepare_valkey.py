"""Author-side preparation library, not a launcher or a validated experiment.

Caller must hold the host campaign lock, check no measurements are running,
enforce storage floors and a build timeout, and supply a fresh output directory.
The source root must be the frozen campaign copy, never evaluator main.
"""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from valkey_aio_overlay import transform as aio_overlay
from valkey_terminal_overlay import transform as terminal_overlay
from valkey_workers_overlay import transform_header, transform_source
from valkey_bio_overlay import transform as bio_overlay
from valkey_control_overlay import transform as control_overlay

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_private(path, transform, manifest):
    before = sha(path)
    text = transform(path.read_text())
    path.write_text(text)
    manifest.append(dict(path=str(path), before=before, after=sha(path)))


def apply_logger(tool, manifest):
    logger = tool / 'memhook'
    for name in ('aio_completion.h', 'wait_events.h', 'wait_window.h', 'valkey_wait_probe.h'):
        target = logger / name
        if target.exists():
            raise FileExistsError(target)
        shutil.copy2(HERE / name, target)
        manifest.append(dict(path=str(target), before=None, after=sha(target)))
    patch_private(logger / 'memhook.h',
                  lambda text: terminal_overlay(aio_overlay(text, with_waits=True)), manifest)


def apply_workers(work, manifest):
    for name, transform in (('io_threads.h', transform_header),
                            ('io_threads.c', transform_source),
                            ('bio.c', bio_overlay), ('debug.c', control_overlay)):
        patch_private(work / 'src' / name, transform, manifest)


def prepare(root, out, variant, logging, jobs=8):
    root, out = Path(root).resolve(), Path(out).resolve()
    if variant not in ('baseline', 'optimized') or not 1 <= jobs <= 24:
        raise ValueError('invalid variant/jobs')
    if out == root or root in out.parents:
        raise ValueError('build output must be outside frozen source')
    # Frozen-source checks for the reused semantic instrumentation and I/O code.
    for relative, expected in {
        'artifact/lib/valkey_trace.py': 'c5b443efad973913a9fc60dd55edbbcce2d96898afc0eae48ae21b427cd9aef0',
        'artifact/vendor/valkey/src/io_threads.c': 'a72f1316e3d59fc1cb36aefbf9921dbc9b9d8e7db33a31667828f1b667266294',
    }.items():
        if sha(root / relative) != expected:
            raise ValueError('frozen source mismatch: ' + relative)
    out.mkdir(parents=True, exist_ok=False)
    state = dict(status='preparing', variant=variant, logging=logging,
                 allocator='jemalloc', overlays=[], binaries={},
                 native_validated=False, source_root=str(root))
    def save():
        (out / 'preparation.json').write_text(json.dumps(state, indent=2) + '\n')
    save()
    try:
        sys.path.insert(0, str(root / 'artifact'))
        from lib import valkey_trace as trace
        from lib import valkey_trace_support as support
        source = out / 'source'
        support.copy_clean_valkey(root / 'artifact/vendor/valkey', source)
        # The frozen vendor snapshot carries configure.ac, not configure.
        # Match the existing instrumentation compile-helper's bootstrap in
        # plain builds as well; keep jemalloc's normal Valkey configure flags.
        jemalloc = source / 'deps/jemalloc'
        if not (jemalloc / 'configure').exists():
            state['jemalloc_bootstrap'] = ['autoconf']
            with (out / 'jemalloc-autoconf.log').open('x') as log:
                subprocess.run(['autoconf'], cwd=jemalloc, stdout=log,
                               stderr=subprocess.STDOUT, check=True)
            state['jemalloc_configure_sha256'] = sha(jemalloc / 'configure')
            save()
        if variant == 'optimized':
            command = ['patch', '--batch', '-p1', '-i', str(root / 'artifact/patches/valkey-B1C1_64.patch')]
            state['optimization_command'] = command
            with (out / 'patch.log').open('w') as log:
                subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT, check=True)
        work = out / 'work-valkey'
        if logging:
            tool = trace.prepare_toolchain(root, out)
            apply_logger(tool, state['overlays'])
            save()
            support.instrument_valkey(source, work, out, str(jobs), 'jemalloc')
            trace.preserve_allocator_semantics(work, variant == 'optimized')
            apply_workers(work, state['overlays'])
            save()
            support.build_instrumented_valkey(work, out / 'build.log', str(jobs), 'jemalloc')
            state['binaries'][str(tool / 'memhook/libmemhook.so')] = sha(tool / 'memhook/libmemhook.so')
        else:
            support.build_baseline_valkey(source, work, out / 'build.log', str(jobs), 'jemalloc')
        for name in ('valkey-server', 'valkey-cli'):
            binary = work / 'src' / name
            state['binaries'][str(binary)] = sha(binary)
        state['status'] = 'built_not_native_validated'
        save()
        return state
    except BaseException as error:
        state['status'] = 'failed'
        state['error'] = repr(error)
        save()
        raise
