"""The fourteen diagnosed zero-extent/nested-lifetime converter cases."""
import hashlib
from pathlib import Path
import sqlite3
import struct
import subprocess
import tempfile
import unittest
import test_page_sampling


def a(t,addr,size,tp=1):return (10,t*100000,size,addr,1,tp,1)
def f(t,addr):return (0,t*100000,0,addr,0,0,0)


class ZeroExtents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):test_page_sampling.PageSamplingTest.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def convert(self, events, exact=False):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            raw=b''.join(struct.pack('<QQQQHHB3x',*e) for e in reversed(events))
            (root/'binary_dump.txt').write_bytes(raw)
            (root/'typeset_dump.txt').write_text('1072|rocksdb::FdWithKeyRange\n' if exact else '0|NULL\n1|Region\n2|Object\n3|Empty\n')
            (root/'fileset_dump.txt').write_text('91|db/version_set.cc\n' if exact else '0|NULL\n1|regression.cpp\n')
            result=subprocess.run([str(self.binary),'--use-container','--seed','99','-s','1','-t','1','-b','2000'],
                                  cwd=root,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual((root/'binary_dump.txt').read_bytes(),raw)
            with sqlite3.connect(root/'allocs.sqlite') as db:
                self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0],'ok')
                return (db.execute('SELECT TIMESTAMP,ADDRESS,SIZE,isNew,TYPE_ID FROM EVENTS ORDER BY 1,2,4,5,3').fetchall(),
                        db.execute('SELECT * FROM STATS ORDER BY TYPE').fetchall(),
                        db.execute('SELECT TYPE,MAX(SIZE),MIN(SIZE) FROM LINES GROUP BY TYPE ORDER BY TYPE').fetchall())
    def test_nested_and_zero_extent_cases(self):
        b=409600
        cases={
            'duplicate_empty':[a(1,b,0,3),a(2,b,0,3)],
            'empty_then_object_free':[a(1,b,0,3),a(2,b,64,2),f(3,b)],
            'object_then_empty_free':[a(1,b,64,2),a(2,b,0,3),f(3,b)],
            'only_empty_free':[a(1,b,0,3),f(2,b)],
            'empty_inside_slab':[a(1,b,4096),a(2,b+64,0,3),a(3,b+64,32,2),f(4,b)],
            'empty_at_slab_base':[a(1,b,4096),a(2,b,0,3),a(3,b,32,2),f(4,b)],
            'empty_at_slab_end':[a(1,b,4096),a(2,b+4096,0,3),f(3,b)],
            'empty_between_replacements':[a(1,b,64,2),a(2,b,0,3),a(3,b,64,2),f(4,b)],
            'ordinary_free':[a(1,b,64,2),f(2,b)],
            'nested_free':[a(1,b,4096),a(2,b+64,32,2),f(3,b)],
            'overlap_replacement':[a(1,b,4096),a(2,b+64,64,2),a(3,b+128,64,2),a(4,b+96,96,2),f(5,b)],
            'page_crossing':[a(1,b+4000,256,2),f(2,b+4000)],
            'unmatched_free':[f(1,b),a(2,b+64,32,2),f(3,b+64)]}
        for name, events in cases.items():
            with self.subTest(name=name):
                rows,stats,lines=self.convert(events)
                self.assertFalse(any(r[2]==0 for r in rows))
                empty=sum(e[2]==0 and e[-1]==1 for e in events)
                if empty:
                    self.assertIn(('Empty',empty,0),stats)
                    self.assertIn(('Empty',0,0),lines)
                nonempty=[e for e in events if not(e[-1]==1 and e[2]==0)]
                if any(e[-1] for e in nonempty):self.assertEqual(rows,self.convert(nonempty)[0])
                else:self.assertEqual(rows,[])
                if name in ('ordinary_free','empty_then_object_free','object_then_empty_free'):
                    self.assertEqual([r[3] for r in rows],[1,0])
                    self.assertTrue(all(r[2]==64 and r[4]==2 for r in rows))
                if name in ('nested_free','empty_inside_slab','empty_at_slab_base'):
                    self.assertEqual(sorted(r[2] for r in rows if not r[3]),[32,4096])
    def test_exact_rocks_tuple(self):
        rows,stats,_=self.convert([(892,t,0,123836769109504,91,1072,1)
            for t in (1075953369555916,1075953369556076)],exact=True)
        self.assertEqual(rows,[])
        self.assertEqual(stats,[('rocksdb::FdWithKeyRange',2,0)])
