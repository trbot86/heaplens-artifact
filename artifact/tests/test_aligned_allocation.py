"""Real logger coverage for successful and failed POSIX aligned allocation."""
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
class AlignedAllocationTest(unittest.TestCase):
    def test_c_and_cpp_addresses_and_failed_requests(self):
        with tempfile.TemporaryDirectory(prefix='heaplens-aligned-allocation-') as tmp:
            work=Path(tmp)
            def run(cmd,**kw):
                result=subprocess.run(list(map(str,cmd)),capture_output=True,text=True,timeout=60,**kw)
                if result.returncode:
                    raise RuntimeError(result.stdout+'\n'+result.stderr)
                return result.stdout
            run(['g++','-fPIC','-ftls-model=initial-exec','-O2','-DUSE_TEMPLATE','-DMEMHOOK_MAX_BUFFER_SIZE=64',
                 '-shared',ROOT/'memhook/memhook.cpp',ROOT/'memhook/hash.cpp','-lrt','-ldl','-pthread','-o',work/'libmemhook.so'])
            run(['g++','-O2','-DUSE_TEMPLATE','-I'+str(ROOT/'memhook'),
                 ROOT/'artifact/tests/fixtures/aligned_allocation.cpp','-L'+str(work),'-Wl,-rpath='+str(work),
                 '-lmemhook','-o',work/'probe'])
            output=run([work/'probe'],cwd=work,env=dict(os.environ,LD_PRELOAD=str(work/'libmemhook.so')))
            targets={name:int(ptr,16) for name,ptr in re.findall(r'target (\w+) (0x[0-9a-f]+)',output)}
            self.assertEqual(set(targets),{'c','cpp'})
            fmt=struct.Struct('<QQQQHH?3x');raw=(work/'binary_dump.txt').read_bytes()
            self.assertEqual(len(raw)%fmt.size,0)
            rows=list(fmt.iter_unpack(raw))
            for address in targets.values():
                history=[r for r in rows if r[3]==address]
                self.assertEqual([r[6] for r in history],[True,False])
                self.assertEqual(history[0][2],64)
            forbidden={0x12345678,0x87654321}
            forbidden.update(int(p,16) for p in re.findall(r'(?:error_)?slot \w+ (0x[0-9a-f]+)',output))
            self.assertFalse(any(r[6] and r[3] in forbidden for r in rows))

if __name__=='__main__':unittest.main()
