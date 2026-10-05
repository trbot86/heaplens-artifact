"""Real-source preservation, synthetic timelines, and native C++ aggregation."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART))
from lib import rocksdb_timing as timing


def fixture(workers=3, delayed=True):
    rows = [dict(logical_id=0, os_tid=74, excluded=True, start_us=1000001,
                 finish_us=5000000 if delayed else 1500000, operations=7)]
    rows += [dict(logical_id=i, os_tid=74+i, excluded=False, start_us=1000000,
                  finish_us=2100000, operations=90) for i in range(1, workers)]
    end = 5100000 if delayed else 2200000
    elapsed = (end - 1000000) / 1e6
    operations = 90 * (workers - 1)
    summary = dict(schema=1, native_start_us=1000000, native_finish_us=end,
                   reader_start_us=1000000, reader_finish_us=2100000,
                   reader_operations=operations, reader_workers=workers-1,
                   writer_start_us=1000001, writer_finish_us=rows[0]['finish_us'],
                   writer_operations=7, writer_workers=1)
    return (f'readwhilewriting : 1.000 micros/op {int(operations/elapsed)} ops/sec '
            f'{elapsed:.3f} seconds {operations} operations;\n' +
            ''.join('HL_HSL_WORKER ' + json.dumps(r) + '\n' for r in rows) +
            'HL_HSL_TIMING ' + json.dumps(summary) + '\n')


class Timing(unittest.TestCase):
    def test_actual_source_preserves_native_methods(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'tools/db_bench_tool.cc'
            source.parent.mkdir()
            with source.open('w', newline='\n') as stream:
                stream.write((ART / 'vendor/rocksdb-historical/tools/db_bench_tool.cc').read_text())
            subprocess.run(['git', 'apply', '--include=tools/db_bench_tool.cc',
                            str(ART / 'patches/rocksdb-historical.patch')],
                           cwd=tmp, check=True, capture_output=True, timeout=30)
            old = source.read_text()
        new = timing.patch(old)
        for start, end in [('  void Start(int id)', '  void AddMessage'),
                           ('  void Report(const Slice& name)', '\n};'),
                           ('    // Stats for some threads can be excluded.', '    merge_stats.Report(name);')]:
            def section(s):
                a = s.index(start)
                return s[a:s.index(end, a) + len(end)]
            self.assertEqual(section(old), section(new))
        self.assertLess(new.index('arg->hl_os_tid ='), new.index('shared->num_initialized++'))
        self.assertGreater(new.index('HlHslTiming timing;'), new.index('merge_stats.Report(name);'))
        with self.assertRaises(ValueError): timing.patch(new)
        with self.assertRaises(ValueError): timing.patch(old + '// changed\n')

    def test_early_and_delayed_writer_have_same_reader_rate(self):
        delayed, early = (timing.parse(fixture(delayed=d), 3) for d in (True, False))
        self.assertAlmostEqual(delayed['reader_only_throughput'], 180 / 1.1)
        self.assertEqual(delayed['reader_only_throughput'], early['reader_only_throughput'])
        self.assertEqual(delayed['writer_tail_after_readers_seconds'], 2.9)
        self.assertEqual(early['writer_tail_after_readers_seconds'], 0)
        self.assertEqual(delayed['native_post_worker_gap_seconds'], .1)
        self.assertNotEqual(delayed['native_throughput'], early['native_throughput'])

    def test_bad_count_role_identity_endpoint_and_duplicate_rejected(self):
        good = fixture()
        for bad in (good.replace('"reader_operations": 180', '"reader_operations": 181'),
                    good.replace('"logical_id": 0', '"logical_id": 2'),
                    good.replace('"os_tid": 74', '"os_tid": 75'),
                    good.replace('"excluded": true', '"excluded": false'),
                    good.replace('"native_finish_us": 5100000', '"native_finish_us": 5000000'),
                    good.replace('HL_HSL_TIMING ', 'MISSING '), good + good):
            with self.subTest(bad=bad[:80]), self.assertRaises(ValueError): timing.parse(bad, 3)

    @unittest.skipUnless(sys.platform.startswith('linux') and shutil.which('g++'), 'Linux g++ required')
    def test_compiled_timeline_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / 'timeline'
            subprocess.run(['g++', '-std=c++11', '-I' + str(ART / 'lib'),
                            str(ART / 'tests/fixtures/hsl_timing.cpp'), '-o', str(binary)],
                           check=True, timeout=60)
            subprocess.run([str(binary)], check=True, capture_output=True, timeout=10)


if __name__ == '__main__': unittest.main()
