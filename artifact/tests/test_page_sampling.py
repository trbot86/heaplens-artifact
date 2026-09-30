"""Converter/reader regressions; Linux with g++, sqlite3/TBB and server dependencies.

Run: python3 -m unittest discover -s artifact/tests -p test_page_sampling.py -v
All inputs and build products are created in temporary directories.
"""
import collections
import pathlib
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
EVENT = struct.Struct('<QQQQHH?3x')  # memory_event_t, Linux x86-64


class PageSamplingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='heaplens-sampling-test-')
        cls.binary = pathlib.Path(cls.build.name) / 'convert'
        source = ROOT / 'type_analysis/convert_to_db'
        subprocess.run(['g++', '-std=c++17', '-O1', *map(str, sorted(source.glob('*.cpp'))),
                        '-lsqlite3', '-lpthread', '-ltbb', '-o', str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def convert(self, probability, minimum, seed=17, pages=40, raw_override=None, perf_address=None):
        # Many events per page, two types sharing every page, and address reuse.
        events = []
        for page in range(1, pages + 1):
            for offset, type_id in ((0, 1), (64, 2), (128, 1), (192, 2)):
                for alloc in (True, False, True, False):
                    events.append(EVENT.pack(1, 1000 + len(events)*1000, 32,
                                             page*4096 + offset, 1, type_id, alloc))
        raw = b''.join(events) if raw_override is None else raw_override
        with tempfile.TemporaryDirectory(prefix='heaplens-sampling-input-') as tmp:
            path = pathlib.Path(tmp)
            (path / 'binary_dump.txt').write_bytes(raw)
            (path / 'typeset_dump.txt').write_text('1|A\n2|B\n')
            (path / 'fileset_dump.txt').write_text('1|fixture.cpp\n')
            command = [str(self.binary), '--sample', str(probability),
                       '--num-pages-per-type', str(minimum), '--num-buckets', '16']
            if seed is not None:
                command += ['--seed', str(seed)]
            if perf_address is not None:
                (path / 'perf.txt').write_text(f'0 0x{perf_address:x} fixture 0 100.00% 0 0 0 0 7 8\n')
                command += ['--perf-file', 'perf.txt']
            result = subprocess.run(command, cwd=path, capture_output=True, text=True, check=True)
            self.assertEqual((path / 'binary_dump.txt').read_bytes(), raw)
            actual_seed = int(re.search(r'Page-sampling seed: (\d+)', result.stderr)[1])
            with sqlite3.connect(path / 'allocs.sqlite') as db:
                self.assertEqual(db.execute("SELECT type FROM sqlite_master WHERE name='SUPERTABLE'").fetchone()[0], 'view')
                self.assertEqual(db.execute('SELECT count(*) FROM EVENTS').fetchone(),
                                 db.execute('SELECT count(*) FROM SUPERTABLE').fetchone())
                self.assertEqual(db.execute('SELECT count(*) FROM FILE_NAMES').fetchone()[0], 2)
                tables = {name: sorted(db.execute('SELECT * FROM ' + name).fetchall())
                          for name in ('SUPERTABLE', 'STATS', 'ALIGNMENT', 'LINES', 'PERF')}
        return tables, actual_seed

    def test_original_extent_survives_sampling_and_frees(self):
        start, size = 4096 - 16, 4096 + 32
        raw = b''.join(EVENT.pack(7, ts, size, start, 1, 1, alloc)
                       for ts, alloc in ((1000, True), (2000, False), (3000, True), (4000, False)))
        for probability, minimum in ((1, 0), (0, 2)):
            tables, _ = self.convert(probability, minimum, raw_override=raw)
            rows = tables['SUPERTABLE']
            self.assertEqual(len(rows), (3 if probability else 2) * 4)
            for row in rows:
                self.assertEqual(row[4], start)
                self.assertEqual(row[8], size)
                self.assertLessEqual(row[3], 4096)

    def test_lookup_readers_and_repeated_conversion(self):
        sys.path.insert(0, str(ROOT/'sifter_vis_d3/server'))
        from sampler import Sampler
        from export_page_snapshots import load_actual_sizes
        with tempfile.TemporaryDirectory(prefix='heaplens-schema-test-') as tmp:
            path = pathlib.Path(tmp)
            raw = b''.join(EVENT.pack(7, ts, 8192, 4080, 1, 1, alloc)
                           for ts, alloc in ((1000, True), (2000, False)))
            (path/'binary_dump.txt').write_bytes(raw)
            (path/'typeset_dump.txt').write_text('1|Node\n')
            (path/'fileset_dump.txt').write_text('1|source.cpp\n')
            # Exercise replacement of an old table and then of a new view.
            with sqlite3.connect(path/'allocs.sqlite') as db:
                db.execute('CREATE TABLE SUPERTABLE(FILE TEXT)')
            for _ in range(2):
                subprocess.run([str(self.binary),'--seed','17','--num-buckets','16'],
                               cwd=path,capture_output=True,check=True)
                self.assertEqual((path/'binary_dump.txt').read_bytes(),raw)
            s = Sampler(str(path/'allocs.sqlite'),num_buckets=16)
            subprocess.run([sys.executable,str(ROOT/'artifact/check_database.py'),str(path/'allocs.sqlite')],
                           capture_output=True,check=True)
            objects = s.get_objects(s.all_data)
            self.assertEqual(len(objects),3)
            self.assertEqual(set(objects.actualSize),{8192})
            self.assertEqual(set(objects.actualAddr),{4080})
            self.assertEqual(set(objects.file),{'source.cpp'})
            self.assertEqual(set(objects.type),{'Node'})
            self.assertEqual(len(s.get_records_in_interval(0,2000)),6)
            self.assertEqual(load_actual_sizes(path/'allocs.sqlite'),{('Node',4080,1000):8192})
            pages = s.get_sample_of_pages(0,2000,{'Node':True})
            self.assertTrue(pages['page_num_events'])
            for page in pages['page_num_events'].values():
                self.assertTrue(all(e['actualSize']==8192 for e in page['events']))
            # A pre-change database remains readable, but carries no invented extent.
            old = path/'legacy.sqlite'
            with sqlite3.connect(path/'allocs.sqlite') as source, sqlite3.connect(old) as db:
                source.backup(db)
                db.executescript('CREATE TABLE LEGACY AS SELECT FILE,LINE,TIMESTAMP,SIZE,ACTUALADDR,ADDRESS,isNew,TYPE FROM SUPERTABLE;'
                                 'DROP VIEW SUPERTABLE; ALTER TABLE LEGACY RENAME TO SUPERTABLE;')
            legacy = Sampler(str(old),num_buckets=16)
            self.assertEqual(set(legacy.get_objects(legacy.all_data).actualSize),{0})
            self.assertEqual(s.get_cache_data(32768,8),legacy.get_cache_data(32768,8))

    @staticmethod
    def pages(rows):
        return {row[5] // 4096 for row in rows}

    def test_distinct_minimum_and_complete_page_histories(self):
        full, _ = self.convert(1, 0)
        for seed in range(20):
            for minimum in (1, 2, 5):
                with self.subTest(seed=seed, minimum=minimum):
                    base, _ = self.convert(.04, 0, seed)
                    sampled, _ = self.convert(.04, minimum, seed)
                    rows = sampled['SUPERTABLE']
                    selected = self.pages(rows)
                    self.assertTrue(self.pages(base['SUPERTABLE']) <= selected)
                    for type_name in ('A', 'B'):
                        self.assertGreaterEqual(len(self.pages([r for r in rows if r[7] == type_name])), minimum)
                    self.assertEqual(collections.Counter(rows), collections.Counter(
                        r for r in full['SUPERTABLE'] if r[5] // 4096 in selected))
                    for table in ('STATS', 'ALIGNMENT', 'LINES'):
                        self.assertEqual(sampled[table], full[table])

    def test_shared_pages_and_probability_endpoints(self):
        for minimum, expected in ((0, 0), (1, 1), (2, 2), (99, 3)):
            sampled, _ = self.convert(0, minimum, pages=3)
            self.assertEqual(len(self.pages(sampled['SUPERTABLE'])), expected)
            self.assertEqual(len(sampled['SUPERTABLE']), expected*16)
        full, _ = self.convert(1, 0, pages=3)
        self.assertEqual(len(full['SUPERTABLE']), 48)

    def test_seed_replay_and_fresh_default(self):
        first, seed = self.convert(.4, 0, seed=None)
        replay, _ = self.convert(.4, 0, seed=seed)
        self.assertEqual(first, replay)
        samples = [self.convert(.4, 0, seed=s)[0]['SUPERTABLE'] for s in (1, 2, 3)]
        self.assertEqual(len({tuple(rows) for rows in samples}), 3)
        # Do not assert that two entropy draws must differ: collisions are legal.
        self.assertGreaterEqual(seed, 0)

    def test_documented_wrapper_forwards_seed(self):
        with tempfile.TemporaryDirectory(prefix='heaplens-wrapper-test-') as tmp:
            path = pathlib.Path(tmp)
            (path/'input').mkdir()
            (path/'type_analysis/bin').mkdir(parents=True)
            shutil.copyfile(ROOT/'sifter.sh', path/'sifter.sh')
            shutil.copy2(self.binary, path/'type_analysis/bin/convert_to_db')
            (path/'type_analysis/Makefile').write_text('bin/convert_to_db:\n\t@true\n')
            (path/'input/binary_dump.txt').write_bytes(EVENT.pack(1, 1000, 32, 4096, 1, 1, True))
            (path/'input/typeset_dump.txt').write_text('1|A\n')
            (path/'input/fileset_dump.txt').write_text('1|fixture.cpp\n')
            result = subprocess.run(['bash', 'sifter.sh', 'input', '-d', '--sample', '0',
                                     '--pages-per-type', '2', '--seed', '0'], cwd=path,
                                    capture_output=True, text=True, check=True)
            self.assertIn('Page-sampling seed: 0', result.stderr)
            with sqlite3.connect(path/'type_analysis/allocs.sqlite') as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM SUPERTABLE').fetchone()[0], 1)

    def test_perf_selected_pages_survive_with_sampling_disabled(self):
        for minimum, expected_pages in ((0, 1), (2, 2)):
            sampled, _ = self.convert(0, minimum, pages=10, perf_address=4*4096)
            self.assertIn(4, self.pages(sampled['SUPERTABLE']))
            self.assertEqual(len(self.pages(sampled['SUPERTABLE'])), expected_pages)
            self.assertEqual(len(sampled['SUPERTABLE']), expected_pages*16)
            self.assertEqual(sampled['PERF'], [(4*4096, 100.0, 7, 8)])

    def test_cross_page_allocations_and_rare_type(self):
        raw = b''.join(EVENT.pack(1, ts, size, address, 1, type_id, alloc)
                       for ts, size, address, type_id, alloc in (
                           (1000, 64, 2*4096-16, 1, True),
                           (2000, 32, 5*4096, 2, True),
                           (3000, 64, 2*4096-16, 1, False),
                           (4000, 32, 5*4096, 2, False),
                           (5000, 32, 7*4096, 1, True),
                           (6000, 32, 7*4096, 1, False)))
        full, _ = self.convert(1, 0, raw_override=raw)
        sampled, _ = self.convert(0, 2, raw_override=raw)
        selected = self.pages(sampled['SUPERTABLE'])
        self.assertEqual(len(self.pages([r for r in sampled['SUPERTABLE'] if r[7] == 'A'])), 2)
        self.assertEqual(self.pages([r for r in sampled['SUPERTABLE'] if r[7] == 'B']), {5})
        self.assertEqual(collections.Counter(sampled['SUPERTABLE']), collections.Counter(
            r for r in full['SUPERTABLE'] if r[5]//4096 in selected))
        for table in ('STATS', 'ALIGNMENT', 'LINES'):
            self.assertEqual(sampled[table], full[table])

    def test_invalid_probability_rejected_before_opening_input(self):
        with tempfile.TemporaryDirectory(prefix='heaplens-invalid-sample-test-') as tmp:
            for probability in ('-0.1', '1.1'):
                result = subprocess.run([str(self.binary), '--sample', probability], cwd=tmp,
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('--sample', result.stderr)
                self.assertFalse((pathlib.Path(tmp)/'allocs.sqlite').exists())


if __name__ == '__main__':
    unittest.main()
