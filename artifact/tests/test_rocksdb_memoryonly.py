"""Memory-only option equivalence and fail-closed persistence checks."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART))
import ae
from lib import rocksdb_memoryonly as rocks


class MemoryOnly(unittest.TestCase):
    def test_templates_preserve_factory_and_arena(self):
        for kind in ('prefix_hash', 'skip_list'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                original = ART / 'config/rocksdb-memoryonly' / (kind + '.ini')
                out = Path(tmp) / 'options.ini'
                rocks.write_options(original, out, 20, 64)
                expected = rocks.read_options(original)
                expected[('DBOptions', 'max_background_jobs')] = '5'
                expected[('CFOptions "default"', 'prefix_extractor')] = 'rocksdb.FixedPrefix.64'
                if kind == 'prefix_hash': expected[('TableOptions/PlainTable "default"', 'user_key_len')] = '64'
                self.assertEqual(rocks.read_options(out), expected)
                self.assertEqual(expected[('CFOptions "default"', 'arena_block_size')], '1048576')
                self.assertEqual(expected[('CFOptions "default"', 'write_buffer_size')], '49928994816')
                if kind == 'prefix_hash':
                    self.assertIn('bucket_count=1048576;', expected[('CFOptions "default"', 'memtable_factory')])
                self.assertNotIn(('DBOptions', 'listeners'), expected)
                with self.assertRaises(FileExistsError): rocks.write_options(original, out, 20, 64)

    def fixture(self, root):
        trial = root / 'trial'; db = trial / 'db'; db.mkdir(parents=True)
        requested = ART / 'config/rocksdb-memoryonly/skip_list.ini'
        shutil.copyfile(requested, db / 'OPTIONS-000007')
        (db / 'LOG').write_text('Options.avoid_flush_during_shutdown: 1\n')
        (db / '000004.log').touch()
        return trial, db, requested

    def test_clean_lifetime_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            trial, _, requested = self.fixture(Path(tmp))
            receipt = rocks.validate(trial, requested)
            self.assertEqual(receipt['status'], 'passed')
            self.assertEqual(receipt['wal_file_bytes'], {'000004.log': 0})

    def test_all_persistence_signals_fail(self):
        signals = ['flush_started', 'flush_finished', 'compaction_started', 'compaction_finished',
                   'table_file_creation', 'table_file_deletion', 'sst', 'blob', 'wal', 'changed_options', 'shutdown']
        for signal in signals:
            with self.subTest(signal=signal), tempfile.TemporaryDirectory() as tmp:
                trial, db, requested = self.fixture(Path(tmp))
                if signal in ('sst', 'blob'):
                    (db / 'nested').mkdir(); (db / 'nested' / ('000009.' + signal)).touch()
                elif signal == 'wal': (db / '000004.log').write_bytes(b'wal payload')
                elif signal == 'changed_options':
                    path = db / 'OPTIONS-000007'
                    path.write_text(path.read_text().replace('write_buffer_size=49928994816', 'write_buffer_size=134217728'))
                elif signal == 'shutdown': (db / 'LOG').write_text('Options.avoid_flush_during_shutdown: 0\n')
                else:
                    with (db / 'LOG').open('a') as out: out.write('EVENT_LOG_v1 ' + json.dumps({'event': signal}) + '\n')
                with self.assertRaises(RuntimeError): rocks.validate(trial, requested)

    def test_jemalloc_hash_and_environment(self):
        allocator = ART / 'vendor/heaplens-allocators/libjemalloc-heaplens.so'
        with patch.dict(os.environ, {'LD_LIBRARY_PATH': 'bad', 'HEAPLENS_DIAGNOSTIC_OUTPUT': 'bad', 'LD_PRELOAD': 'bad'}):
            env = rocks.environment(allocator)
        self.assertEqual(env['LD_PRELOAD'], str(allocator))
        self.assertNotIn('LD_LIBRARY_PATH', env)
        self.assertNotIn('HEAPLENS_DIAGNOSTIC_OUTPUT', env)
        self.assertEqual(env['GLIBC_TUNABLES'], 'glibc.rtld.optional_static_tls=4194304')
        with tempfile.NamedTemporaryFile() as bad, self.assertRaises(RuntimeError): rocks.environment(bad.name)

    def test_insufficient_memory_fails(self):
        with patch.object(Path, 'is_file', return_value=False), patch.object(Path, 'read_text', return_value='MemAvailable: 1024 kB\n'):
            with self.assertRaises(RuntimeError): rocks.check_memory()

    def test_inline_skiplist_default_matches_verified_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); out = root / 'out'; out.mkdir()
            vendor = root / 'vendor'; src = vendor / 'rocksdb-historical'
            (src / 'memtable').mkdir(parents=True)
            for name in ('Makefile', 'memtable/inlineskiplist.h'):
                (src / name).write_text('ALIGN_TALL_NODE SEG_TALL_NODE\n')
            allocator = vendor / 'heaplens-allocators/libjemalloc-heaplens.so'
            allocator.parent.mkdir(); allocator.write_bytes(b'fixture')
            builds, commands = [], []

            def fake_run(cmd, *, cwd, log, **kwargs):
                if cmd[0] == 'make':
                    builds.append(cmd); (cwd / 'db_bench').write_bytes(b'fixture')
                elif cmd[0] == 'numactl':
                    commands.append(cmd)
                    log.write_text('readwhilewriting : 1 micros/op 100 ops/sec\n')
            args = ae.parse_args(['rocksdb', '--memtable', 'skip_list', '--profile', 'paper', '--reps', '1'])
            with patch.object(ae, 'VENDOR', vendor), patch.object(ae, 'run', side_effect=fake_run), \
                 patch.object(ae, 'node_cpus', return_value=list(range(20))) as cpus, \
                 patch.object(rocks, 'environment', return_value={'LD_PRELOAD': str(allocator)}), \
                 patch.object(rocks, 'check_memory', return_value=128*1024**3), \
                 patch.object(rocks, 'validate', return_value={'status': 'passed'}), \
                 patch.object(ae.time, 'sleep'), redirect_stdout(io.StringIO()):
                ae.rocksdb(args, out)
            cpus.assert_called_once_with(0, 20, None)
            self.assertIn('ALIGN_TALL_NODE=3', builds[1]); self.assertIn('SEG_TALL_NODE=3', builds[1])
            for cmd in commands:
                for flag in ('--threads=19', '--num=10000000', '--duration=60', '--key_size=32', '--value_size=128', '--disable_wal=1', '--sync=0'):
                    self.assertIn(flag, cmd)
                self.assertFalse(any('waitforcompaction' in str(arg) for arg in cmd))


if __name__ == '__main__': unittest.main()
