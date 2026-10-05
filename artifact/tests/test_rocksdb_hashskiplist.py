"""HashSkipList protocol, topology, and effective-options regression tests."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART))
import ae
from lib import rocksdb_hashskiplist as hsl
from lib import rocksdb_memoryonly as memory
from lib import rocksdb_timing as timing
from test_rocksdb_timing import fixture as timing_fixture


class HashSkipList(unittest.TestCase):
    def topology(self, sockets):
        # 24 cores/socket, two siblings/core, deliberately noncontiguous SMT IDs.
        return '\n'.join(f'{node*24+core+smt*sockets*24},{node},{node*24+core},Y'
                         for smt in range(2) for node in range(sockets) for core in range(24))

    def test_pyke_and_jax_topologies(self):
        for sockets in (2, 4):
            with self.subTest(sockets=sockets), \
                 patch.object(hsl.subprocess, 'check_output', return_value=self.topology(sockets)), \
                 patch.object(os, 'sched_getaffinity', create=True, return_value=set(range(sockets*48))):
                selected = hsl.cpus([0, 1], 96)
                expected = sorted(list(range(48)) + list(range(sockets*24, sockets*24+48)))
                self.assertEqual(selected, expected)
                self.assertEqual(hsl.cpus([0, 1], 8), [0, 1, 24, 25, sockets*24, sockets*24+1, sockets*24+24, sockets*24+25])
                explicit = ','.join(map(str, selected))
                self.assertEqual(hsl.cpus([0, 1], 96, explicit), selected)

    def test_cpu_constraints(self):
        with patch.object(hsl.subprocess, 'check_output', return_value=self.topology(4)), \
             patch.object(os, 'sched_getaffinity', create=True, return_value=set(range(192))):
            for nodes, count, cpus in (([0, 0], 96, None), ([0, 1], 3, None),
                                       ([0, 1], 4, '0-3'), ([0, 1], 4, '0,0,24,25'),
                                       ([0, 1], 4, '0,1,48,49'), ([0, 1], 4, '0,-1'),
                                       ([0, 1], 4, '0,1,24-1000000')):
                with self.subTest(nodes=nodes, count=count, cpus=cpus), self.assertRaises(ValueError):
                    hsl.cpus(nodes, count, cpus)
        with patch.object(hsl.subprocess, 'check_output', return_value=self.topology(2)), \
             patch.object(os, 'sched_getaffinity', create=True, return_value=set(range(48))):
            with self.assertRaises(RuntimeError): hsl.cpus([0, 1], 96)

    def test_node_argument_scope(self):
        for argv in (['rocksdb', '--rocks-nodes', '0', '0'],
                     ['rocksdb', '--rocks-nodes', '-1', '1'],
                     ['rocksdb', '--memtable', 'skip_list', '--rocks-nodes', '0', '1'],
                     ['hnsw', '--rocks-nodes', '0', '1']):
            with self.subTest(argv=argv), patch('sys.stderr', io.StringIO()), self.assertRaises(SystemExit):
                ae.parse_args(argv)
        self.assertEqual(ae.parse_args(['all-performance', '--rocks-nodes', '2', '3']).rocks_nodes, [2, 3])

    def fixture(self, root):
        db = root / 'db'; db.mkdir()
        text = (ART / 'config/rocksdb-memoryonly/prefix_hash.ini').read_text()
        text = text.replace('write_buffer_size=49928994816', 'write_buffer_size=268435456')
        text = text.replace('disable_auto_compactions=true', 'disable_auto_compactions=false')
        text = text.replace('avoid_flush_during_shutdown=true', 'avoid_flush_during_shutdown=false')
        (db / 'OPTIONS-000007').write_text(text)
        (db / 'LOG').write_text('fixture\n')
        (db / '000004.log').touch()
        (db / '000005.sst').touch()
        return db

    def test_flushing_is_allowed_but_wrong_options_and_wal_are_not(self):
        for change in ('none', 'buffer', 'compaction', 'shutdown', 'wal', 'bucket_count', 'prefix'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                trial = Path(tmp); db = self.fixture(trial)
                options = db / 'OPTIONS-000007'
                replacements = {'buffer': ('268435456', '49928994816'),
                                'compaction': ('disable_auto_compactions=false', 'disable_auto_compactions=true'),
                                'shutdown': ('avoid_flush_during_shutdown=false', 'avoid_flush_during_shutdown=true'),
                                'bucket_count': ('bucket_count=1048576', 'bucket_count=1000000'),
                                'prefix': ('rocksdb.FixedPrefix.32', 'rocksdb.FixedPrefix.64')}
                if change in replacements: options.write_text(options.read_text().replace(*replacements[change]))
                if change == 'wal': (db / '000004.log').write_bytes(b'payload')
                if change == 'none':
                    receipt = hsl.validate(trial, 96, 32)
                    self.assertEqual(receipt['status'], 'passed')
                    self.assertEqual(receipt['sst_files'], 1)
                else:
                    with self.assertRaises(RuntimeError): hsl.validate(trial, 96, 32)

    def test_default_driver_matches_verified_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); out = root / 'out'; out.mkdir()
            vendor = root / 'vendor'; src = vendor / 'rocksdb-historical'
            (src / 'memtable').mkdir(parents=True)
            for name in ('Makefile', 'memtable/skiplist.h'): (src / name).write_text('REORDER_FIELDS NO_PADDING_NODE\n')
            allocator = vendor / 'heaplens-allocators/libjemalloc-heaplens.so'
            allocator.parent.mkdir(); allocator.write_bytes(b'fixture')
            builds, commands = [], []

            def fake_run(cmd, *, cwd, log, **kwargs):
                if cmd[0] == 'make':
                    builds.append(cmd); (cwd / 'db_bench').write_bytes(b'fixture')
                elif cmd[0] == 'numactl':
                    commands.append(cmd); log.write_text(timing_fixture(96))

            args = ae.parse_args(['rocksdb', '--profile', 'paper', '--reps', '2'])
            with patch.object(ae, 'VENDOR', vendor), patch.object(ae, 'run', side_effect=fake_run), \
                 patch.object(hsl, 'cpus', return_value=list(range(96))) as cpus, \
                 patch.object(memory, 'environment', return_value={'LD_PRELOAD': str(allocator)}), \
                 patch.object(memory, 'check_memory') as memory_check, \
                 patch.object(memory, 'write_options') as memory_options, \
                 patch.object(timing, 'apply', return_value={'tested': True}) as timing_patch, \
                 patch.object(hsl, 'validate', return_value={'status': 'passed'}) as validation, \
                 patch.object(ae.time, 'sleep'), redirect_stdout(io.StringIO()):
                ae.rocksdb(args, out)
            cpus.assert_called_once_with([0, 1], 96, None)
            memory_check.assert_not_called(); memory_options.assert_not_called()
            self.assertEqual(len(builds), 2)
            self.assertEqual(timing_patch.call_count, 2)
            self.assertEqual(builds[1], builds[0] + ['REORDER_FIELDS=1'])
            self.assertEqual(builds[0][3:], ['DEBUG_LEVEL=0', 'PORTABLE=1', 'DISABLE_WARNING_AS_ERROR=1'])
            self.assertEqual(len(commands), 4); self.assertEqual(validation.call_count, 4)
            for cmd in commands:
                for flag in ('--threads=95', '--num=10000000', '--duration=10', '--key_size=32',
                             '--prefix_size=32', '--value_size=128', '--disable_wal=1', '--sync=0',
                             '--benchmarks=filluniquerandom,waitforcompaction,readwhilewriting',
                             '--interleave=0,1', *hsl.workload_args(96)):
                    self.assertIn(flag, cmd)
                self.assertFalse(any('options_file' in arg for arg in cmd))
            protocol = json.loads((out / 'protocol.json').read_text())
            self.assertEqual(protocol['optimized_flags'], ['REORDER_FIELDS=1'])
            self.assertEqual(protocol['write_buffer_bytes'], 268435456)
            self.assertEqual(protocol['duration_seconds'], 10)
            summary = json.loads((out / 'summary.json').read_text())
            self.assertEqual(summary['variants']['baseline']['mean'], int(90 * 95 / 4.1))
            self.assertAlmostEqual(summary['reader_only']['variants']['baseline']['mean'], 90 * 95 / 1.1)
            self.assertEqual(len(summary['timing_runs']), 4)
            self.assertEqual(len(list(out.glob('*-rep*/timing.json'))), 4)


if __name__ == '__main__': unittest.main()
