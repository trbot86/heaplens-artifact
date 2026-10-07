"""A valid database containing unrelated typed rows must fail Figure 6 coverage."""
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('node_coverage', Path(__file__).resolve().parents[1] / 'check_tpcc_nodes.py')
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)


class NodeCoverage(unittest.TestCase):
    def check_rows(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trace.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE SUPERTABLE(TYPE TEXT, SIZE INTEGER, FILE TEXT, isNew INTEGER)')
                db.executemany('INSERT INTO SUPERTABLE VALUES(?,?,?,?)', rows)
            return coverage.check(path)

    def test_unrelated_typed_allocations_are_insufficient(self):
        with self.assertRaisesRegex(ValueError, 'no typed BCCO'):
            self.check_rows([('row_t', 48, '/src/row.cpp', 1)])

    def test_free_does_not_substitute_for_allocation(self):
        with self.assertRaisesRegex(ValueError, 'no typed BCCO'):
            self.check_rows([('node_t<unsigned long,itemid_t*>', 56, '/src/allocator_new.h', 0)])

    def test_wrong_layout_or_missing_source_fails(self):
        for size, source in [(0, '/src/allocator_new.h'), (56, 'NULL')]:
            with self.subTest(size=size, source=source), self.assertRaises(ValueError):
                self.check_rows([('node_t<unsigned long,itemid_t*>', size, source, 1)])

    def test_expected_node_records_pass(self):
        result = self.check_rows([('node_t<unsigned long, itemid_t*>', 56, '/src/allocator_new.h', 1)] * 7)
        self.assertEqual(result['typed_node_allocations'], 7)


if __name__ == '__main__':
    unittest.main()
