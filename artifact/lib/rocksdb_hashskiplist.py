"""HashSkipList's 256-MiB workload and two-node CPU placement."""
import os
from pathlib import Path
import re
import subprocess

from .rocksdb_memoryonly import read_options, sha

WRITE_BUFFER_BYTES = 268435456


def cpus(nodes, needed, requested=None):
    """Select equal numbers of logical CPUs per node, retaining SMT siblings."""
    if len(nodes) != 2 or len(set(nodes)) != 2 or min(nodes) < 0:
        raise ValueError('HashSkipList requires two distinct nonnegative NUMA nodes')
    if needed < 2 or needed % 2:
        raise ValueError('HashSkipList NUMA placement requires an even total thread count')
    topology = subprocess.check_output(['lscpu', '-p=CPU,NODE,CORE,ONLINE'], text=True)
    allowed = os.sched_getaffinity(0)
    available = {}
    for line in topology.splitlines():
        if not line or line.startswith('#'):
            continue
        cpu, node, core, online = line.split(',')
        if node in {str(n) for n in nodes} and online == 'Y' and int(cpu) in allowed:
            available[int(cpu)] = (int(node), int(core))
    per_node = needed // 2
    if requested is not None:
        selected = []
        for part in requested.split(','):
            if not re.fullmatch(r'[0-9]+(?:-[0-9]+)?', part):
                raise ValueError('--cpus requires CPU IDs/ranges, such as 0-95')
            bounds = list(map(int, part.split('-')))
            start, end = bounds[0], bounds[-1]
            if start > end or end > max(available, default=-1):
                raise ValueError('CPU range is outside the selected nodes')
            selected.extend(range(start, end + 1))
        if len(selected) != needed or len(set(selected)) != needed:
            raise ValueError('--cpus must contain exactly --threads distinct CPU IDs')
        if any(cpu not in available for cpu in selected):
            raise ValueError('Selected CPUs must be online, allowed, and on --rocks-nodes')
        if any(sum(available[cpu][0] == node for cpu in selected) != per_node for node in nodes):
            raise ValueError('HashSkipList requires equal CPU counts on the two selected nodes')
        return selected
    selected = []
    for node in nodes:
        # Group siblings by physical core; do not assume contiguous socket masks.
        candidates = sorted((core, cpu) for cpu, (numa, core) in available.items() if numa == node)
        if len(candidates) < per_node:
            raise RuntimeError(f'NUMA node {node}: need {per_node} available logical CPUs, '
                               f'found {len(candidates)}; use --profile smoke on smaller hosts')
        selected.extend(cpu for _, cpu in candidates[:per_node])
    return sorted(selected)


def workload_args(threads):
    return ['--compression_type=none', '--use_plain_table=1', '--memtablerep=prefix_hash',
            '--max_write_buffer_number=2', f'--write_buffer_size={WRITE_BUFFER_BYTES}',
            '--allow_concurrent_memtable_write=false', f'--max_background_jobs={max(1, threads // 4)}',
            '--compaction_pri=3', '--compaction_style=0', '--bloom_bits=10', '--bloom_locality=1']


def validate(trial, threads, key_size):
    """Check effective workload options and disabled WAL; SSTs are expected."""
    db = Path(trial) / 'db'
    files = sorted(db.glob('OPTIONS-*'))
    if not files:
        raise RuntimeError(f'No effective RocksDB OPTIONS file in {db}')
    actual = read_options(files[-1])
    expected = {}
    for section, values in {
        'DBOptions': {'avoid_flush_during_shutdown': 'false',
                      'allow_concurrent_memtable_write': 'false',
                      'max_background_jobs': str(max(1, threads // 4)), 'info_log_level': 'INFO_LEVEL'},
        'CFOptions "default"': {'write_buffer_size': str(WRITE_BUFFER_BYTES),
                                'max_write_buffer_number': '2', 'disable_auto_compactions': 'false',
                                'table_factory': 'PlainTable', 'arena_block_size': '1048576',
                                'prefix_extractor': f'rocksdb.FixedPrefix.{key_size}',
                                'compression': 'kNoCompression', 'bloom_locality': '1',
                                'compaction_pri': 'kMinOverlappingRatio', 'compaction_style': 'kCompactionStyleLevel',
                                'memtable_factory': '{id=HashSkipListRepFactory;branching_factor=4;skiplist_height=4;bucket_count=1048576;}'},
        'TableOptions/PlainTable "default"': {'user_key_len': str(key_size), 'bloom_bits_per_key': '10'},
    }.items():
        expected.update({(section, key): value for key, value in values.items()})
    differences = {str(key): [value, actual.get(key)] for key, value in expected.items() if actual.get(key) != value}
    if differences:
        raise RuntimeError(f'Effective HashSkipList options differ: {differences}')
    wals = {path.name: path.stat().st_size for path in db.glob('*.log') if path.stem.isdigit()}
    if any(wals.values()):
        raise RuntimeError(f'HashSkipList run produced WAL payload: {wals}')
    return {'status': 'passed', 'options_sha256': sha(files[-1]), 'db_log_sha256': sha(db / 'LOG'),
            'wal_file_bytes': wals, 'sst_files': len(list(db.glob('*.sst'))),
            'scope': '256-MiB HashSkipList; flushing and compaction enabled, WAL disabled.'}
