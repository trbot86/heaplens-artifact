"""Retained-report parsing, preservation and native importer compatibility."""
import importlib.util
import math
from pathlib import Path
import sqlite3
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('perf_example',ROOT/'artifact/perf-c2c-example/example.py')
example=importlib.util.module_from_spec(spec);spec.loader.exec_module(example)


class PerfExample(unittest.TestCase):
    def test_retained_rows_match_database_manifest(self):
        manifest,rows=example.verify()
        self.assertEqual(len(rows),11)
        self.assertEqual(len(manifest['database']['perf_rows']),10)
        self.assertEqual(rows[0x55acc2ca9500],(1.44,1922,1206))

    def test_rejects_wrong_columns_empty_and_duplicate_rows(self):
        original=(example.BUNDLE/'perf_c2c_report_for_db.txt').read_text()
        line=next(line for line in original.splitlines() if '0x55acc2ca9500' in line and '1.44%' in line)
        for text in ('',original.replace(line,line+'\n'+line),original.replace('1.44%','NaN%'),original.replace('1.44%','1.44')):
            with self.assertRaises(ValueError):example.report_rows(text)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(example,'verify',return_value=({},{})):
            marker=Path(tmp)/'original';marker.write_text('keep')
            with self.assertRaises(FileExistsError):example.prepare(Path(tmp))
            self.assertEqual(marker.read_text(),'keep')

    def test_native_import_of_retained_report_format(self):
        # Synthetic allocation events only test the actual converter/parser.
        # Hardware counts/addresses are the unchanged retained report's rows.
        _,expected=example.verify()
        with tempfile.TemporaryDirectory(prefix='heaplens-perf-import-') as tmp:
            root=Path(tmp);binary=root/'convert'
            source=ROOT/'type_analysis/convert_to_db'
            subprocess.run(['g++','-std=c++17','-O1',*map(str,sorted(source.glob('*.cpp'))),
                '-lsqlite3','-lpthread','-ltbb','-o',str(binary)],check=True,timeout=180)
            event=struct.Struct('<QQQQHH?3x')
            raw=b''.join(event.pack(1,100000+i*1000+int(not new)*100,32,address,1,1,new)
                         for i,address in enumerate(expected) for new in (True,False))
            (root/'binary_dump.txt').write_bytes(raw)
            (root/'typeset_dump.txt').write_text('1|PerfExample\n')
            (root/'fileset_dump.txt').write_text('1|synthetic.cpp\n')
            result=subprocess.run([str(binary),'--sample','0','--num-pages-per-type','0','--num-buckets','16','--seed','17',
                '--perf-file',str(example.BUNDLE/'perf_c2c_report_for_db.txt')],cwd=root,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual((root/'binary_dump.txt').read_bytes(),raw)
            with sqlite3.connect(root/'allocs.sqlite') as con:
                actual=con.execute('SELECT CLADDRESS,HITM,LOADS,STORES FROM PERF').fetchall()
                self.assertEqual(len(actual),11)
                for address,hitm,loads,stores in actual:
                    self.assertTrue(math.isclose(hitm,expected[address][0],abs_tol=1e-6))
                    self.assertEqual((loads,stores),expected[address][1:])


if __name__=='__main__':unittest.main()
