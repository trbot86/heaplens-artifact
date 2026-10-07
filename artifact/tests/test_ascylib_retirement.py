"""A real logger/SSMEM test of logical retirement, without a benchmark campaign."""
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]

@unittest.skipUnless(sys.platform.startswith('linux') and shutil.which('g++'), 'Linux native test')
class RetirementTest(unittest.TestCase):
    def test_shared_ssmem_preserves_four_retirements(self):
        with tempfile.TemporaryDirectory(prefix='heaplens-ssmem-retirement-') as tmp:
            work=Path(tmp);lib=work/'shared'
            def run(command, **kw):
                return subprocess.run(list(map(str,command)),check=True,capture_output=True,text=True,timeout=60,**kw).stdout
            run(['bash','-c','source "$1"; prepare_ascylib_trace_ssmem "$2" "$3"','test',
                 ROOT/'artifact/lib/prepare_ascylib.sh',ROOT,lib])
            run(['g++','-fPIC','-ftls-model=initial-exec','-O2','-DMEMHOOK_ASCYLIB','-DMEMHOOK_MAX_BUFFER_SIZE=64',
                 '-shared',ROOT/'memhook/memhook.cpp',ROOT/'memhook/hash.cpp','-lrt','-ldl','-pthread','-o',work/'libmemhook.so'])
            run(['gcc','-fno-pie','-DMEMHOOK_ASCYLIB','-I'+str(ROOT/'memhook'),'-c',
                 ROOT/'artifact/tests/fixtures/ssmem_retirement.c','-o',work/'probe.o'])
            run(['gcc','-no-pie','-Wl,--export-dynamic',work/'probe.o','-L'+str(work),'-Wl,-rpath='+str(work),
                 '-lmemhook','-L'+str(lib),'-Wl,-rpath='+str(lib),'-lssmem_x86_64','-ldl','-pthread','-lrt','-o',work/'probe'])
            symbols=run(['nm','-D',work/'probe'])
            self.assertRegex(symbols,r'(?m)^\s+U ssmem_free$')
            output=run([work/'probe'],cwd=work,env=dict(os.environ,LD_PRELOAD=str(work/'libmemhook.so')))
            targets={int(x,16) for x in re.findall(r'target (0x[0-9a-f]+)',output)}
            self.assertEqual(len(targets),4)
            record=struct.Struct('<QQQQHH?3x');raw=(work/'binary_dump.txt').read_bytes()
            self.assertEqual(len(raw)%record.size,0)
            events={ptr:[] for ptr in targets}
            for row in record.iter_unpack(raw):
                if row[3] in targets:events[row[3]].append(row)
            for history in events.values():
                self.assertEqual([row[6] for row in history],[True,False])
                self.assertLessEqual(history[0][1],history[1][1])

if __name__=='__main__':unittest.main()
