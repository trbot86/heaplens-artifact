"""Read-time field matching must preserve layouts and const/pointer distinctions."""
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'sifter_vis_d3/server'))
from field_type_aliases import FIELD_TYPE_ALIASES, match_field_types
from sampler import Sampler

RUNTIME, EXTRACTED = next(iter(FIELD_TYPE_ALIASES.items()))


class FieldTypeAliasesTest(unittest.TestCase):
    def test_exact_match_takes_precedence(self):
        self.assertEqual(match_field_types({RUNTIME: ['exact'], EXTRACTED: ['alias']},
                                          [RUNTIME]), {RUNTIME: ['exact']})

    def test_distinct_types_are_not_merged(self):
        other = [RUNTIME + '::Node', RUNTIME.replace('charconst*', 'char*const'),
                 RUNTIME.replace('charconst*', 'char*'),
                 RUNTIME.replace('const&>', '&>'),
                 RUNTIME.replace('rocksdb::SkipList', 'other::SkipList')]
        self.assertEqual(match_field_types({EXTRACTED: ['fields']}, other), {})

    def test_database_fields_preserved_for_both_layouts(self):
        # Exercise the real backend query, including the generator caller.
        for previous_offset, height_offset in ((40, 48), (40, 36)):
            with self.subTest(height_offset=height_offset), tempfile.TemporaryDirectory() as tmp:
                path = str(Path(tmp) / 'fields.sqlite')
                with sqlite3.connect(path) as db:
                    db.execute('CREATE TABLE FIELDS(TYPE, SUBTYPE, NAME, SIZE, OFFSET)')
                    db.executemany('INSERT INTO FIELDS VALUES(?,?,?,?,?)', [
                        (EXTRACTED, 'Node**', 'prev_', 8, previous_offset),
                        (EXTRACTED, 'int32_t', 'prev_height_', 4, height_offset),
                        ('Other', 'int', 'unrelated', 4, 0)])
                sampler = Sampler.__new__(Sampler)
                sampler.fname = path
                actual = sampler.get_fields(name for name in [RUNTIME])
                self.assertEqual(set(actual), {RUNTIME})
                self.assertEqual([(f['name'], f['size'], f['offset']) for f in actual[RUNTIME]],
                                 [('prev_', 8, previous_offset), ('prev_height_', 4, height_offset)])
                with sqlite3.connect(path) as db:
                    self.assertEqual(db.execute('SELECT DISTINCT TYPE FROM FIELDS ORDER BY TYPE').fetchall(),
                                     [('Other',), (EXTRACTED,)])


if __name__ == '__main__':
    unittest.main()
