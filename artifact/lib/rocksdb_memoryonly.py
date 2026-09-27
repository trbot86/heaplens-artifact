"""Memory-only db_bench options and post-run persistence checks."""
import configparser
import hashlib
import json
import os
from pathlib import Path
import re

WRITE_BUFFER_BYTES = 49928994816
ALLOCATOR_SHA256 = 'c516606efbdb708f503bc0f249061e492df04010a7292056281a0e9df6cbb3da'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_options(path):
    parser = configparser.ConfigParser(interpolation=None, delimiters=('=',),
                                       comment_prefixes=('#',), strict=True)
    parser.read_string(Path(path).read_text())
    return {(section, key): value for section in parser.sections()
            for key, value in parser[section].items()}


def write_options(template, output, threads, key_size):
    # Keep the validated arena size and complete hash-factory serialization.
    # db_bench does not expose avoid_flush_during_shutdown as a CLI flag.
    text = Path(template).read_text()
    for pattern, replacement in (
        (r'(?m)^  max_background_jobs=\d+$', f'  max_background_jobs={max(1, threads // 4)}'),
        (r'(?m)^  prefix_extractor=rocksdb\.FixedPrefix\.\d+$', f'  prefix_extractor=rocksdb.FixedPrefix.{key_size}'),
    ):
        text, count = re.subn(pattern, replacement, text)
        if count != 1:
            raise RuntimeError(f'Unexpected RocksDB option template: {pattern}')
    if '[TableOptions/PlainTable "default"]' in text:
        text, count = re.subn(r'(?m)^  user_key_len=\d+$', f'  user_key_len={key_size}', text)
        if count != 1:
            raise RuntimeError('Missing plain-table key length in RocksDB option template')
    with Path(output).open('x') as handle:
        handle.write(text)
    return sha(output)


def environment(allocator):
    if sha(allocator) != ALLOCATOR_SHA256:
        raise RuntimeError('RocksDB requires the retained jemalloc 5.3 library')
    env = os.environ.copy()
    for key in ('LD_LIBRARY_PATH', 'PYTHONPATH', 'HEAPLENS_DIAGNOSTIC_OUTPUT'):
        env.pop(key, None)
    env.update(LD_PRELOAD=str(allocator), GLIBC_TUNABLES='glibc.rtld.optional_static_tls=4194304',
               OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4')
    return env


def check_memory():
    """Fail before building a full campaign on a host/container too small for it."""
    info = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    available = int(info['MemAvailable'].split()[0]) * 1024
    for limit_path, used_path in (
        ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory.current'),
        ('/sys/fs/cgroup/memory/memory.limit_in_bytes', '/sys/fs/cgroup/memory/memory.usage_in_bytes'),
    ):
        if Path(limit_path).is_file() and Path(used_path).is_file():
            limit = Path(limit_path).read_text().strip()
            if limit.isdigit():
                available = min(available, int(limit) - int(Path(used_path).read_text()))
    if available < 64 * 1024**3:
        raise RuntimeError('RocksDB paper runs require at least 64 GiB available host/container memory; use --profile smoke for a small check')
    return available


def validate(trial, requested):
    """Inspect the complete fresh-DB lifetime, including process shutdown."""
    db = Path(trial) / 'db'
    log = db / 'LOG'
    text = log.read_text()
    for line in text.splitlines():
        if 'EVENT_LOG_v1 ' in line:
            event = json.loads(line.split('EVENT_LOG_v1 ', 1)[1]).get('event', '')
            if any(word in event for word in ('flush', 'compaction', 'table_file_creation', 'table_file_deletion')):
                raise RuntimeError(f'Memory-only run produced a data-persistence event: {event}; see {log}')
    tables = [str(path) for path in db.rglob('*') if path.suffix.lower() in ('.sst', '.blob')]
    if tables:
        raise RuntimeError(f'Memory-only run produced table/blob files: {tables[:5]}')
    wals = {path.name: path.stat().st_size for path in db.glob('*.log') if path.stem.isdigit()}
    if any(wals.values()):
        raise RuntimeError(f'Memory-only run produced WAL payload: {wals}')
    files = sorted(db.glob('OPTIONS-*'))
    if not files:
        raise RuntimeError(f'No effective RocksDB OPTIONS file in {db}')
    actual, expected = read_options(files[-1]), read_options(requested)
    differences = {str(key): [value, actual.get(key)] for key, value in expected.items()
                   if actual.get(key) != value}
    if differences:
        raise RuntimeError(f'Effective RocksDB options differ: {differences}')
    required = {('DBOptions', 'avoid_flush_during_shutdown'): 'true',
                ('CFOptions "default"', 'disable_auto_compactions'): 'true',
                ('CFOptions "default"', 'write_buffer_size'): str(WRITE_BUFFER_BYTES)}
    if any(actual.get(key) != value for key, value in required.items()):
        raise RuntimeError('Effective RocksDB options do not disable data persistence')
    if not re.search(r'Options\.avoid_flush_during_shutdown:\s*1\b', text):
        raise RuntimeError('DB log does not confirm shutdown flushing is disabled')
    return {'status': 'passed', 'flush_compaction_table_events': 0, 'sst_blob_files': 0,
            'wal_file_bytes': wals, 'db_log_sha256': sha(log), 'options_sha256': sha(files[-1]),
            'scope': 'No data flushing, compaction, tables or WAL payload; metadata and diagnostic writes remain.'}
