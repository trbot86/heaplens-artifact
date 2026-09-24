"""Local Linux regression checks for TPC-C's separate allocation path; no PMU needed."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ART = Path(__file__).resolve().parents[1]
ROOT = ART.parent
VENDOR = ART / 'vendor/setbench'
EXPECTED = 'c516606efbdb708f503bc0f249061e492df04010a7292056281a0e9df6cbb3da'


class RetainedAllocator(unittest.TestCase):
    def test_retained_binary_checksum(self):
        lib = ART / 'vendor/heaplens-allocators/libjemalloc-heaplens.so'
        self.assertEqual(hashlib.sha256(lib.read_bytes()).hexdigest(), EXPECTED)


@unittest.skipUnless(sys.platform.startswith('linux') and shutil.which('g++'),
                     'requires Linux and g++')
class SeparateAllocator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (VENDOR / 'common/recordmgr/globals.h').exists():
            raise unittest.SkipTest('initialize SetBench recordmgr submodule first')
        cls.temp = tempfile.TemporaryDirectory(prefix='heaplens-allocator-test-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.source = Path(cls.temp.name)
        cls.cwd = cls.source / 'macrobench'; cls.cwd.mkdir()
        libs = cls.source / 'lib'; libs.mkdir()
        for name in ('libjemalloc.so', 'libmimalloc.so'):
            shutil.copy2(VENDOR / 'lib' / name, libs / name)
        subprocess.run(['bash', '-c', 'set -euo pipefail; source "$1"; tpcc_stage_allocators "$2" "$3"',
                        'stage', str(ART / 'lib/tpcc_allocators.sh'), str(ROOT), str(cls.source)], check=True)
        common = ['g++', '-std=c++17', '-O1', '-DMEMHOOK_SEG_DS',
                  '-I' + str(ART / 'patches/setbench-tpcc/common/recordmgr'),
                  '-I' + str(VENDOR / 'common/recordmgr'), '-I' + str(VENDOR / 'common'),
                  str(ART / 'tests/fixtures/tpcc_allocator_probe.cpp'), '-ldl', '-pthread']
        cls.good = cls.source / 'good'; cls.bad = cls.source / 'bad'
        cls.mimalloc = cls.source / 'mimalloc'
        subprocess.run([*common, '-o', str(cls.good)], check=True)
        subprocess.run([*common, '-DMEMHOOK_SEG_DS_LIB="../lib/libjemalloc.so"', '-o', str(cls.bad)], check=True)
        subprocess.run([*common, '-DUSE_MIMALLOC', '-o', str(cls.mimalloc)], check=True)

    def run_probe(self, binary, preload):
        env = dict(os.environ, LD_PRELOAD=str(self.source / 'lib' / preload),
                   GLIBC_TUNABLES='glibc.rtld.optional_static_tls=4194304')
        return subprocess.run([str(binary)], cwd=self.cwd, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)

    def test_staging_preserves_global_libraries(self):
        for name in ('libjemalloc.so', 'libmimalloc.so'):
            self.assertEqual((self.source / 'lib' / name).read_bytes(), (VENDOR / 'lib' / name).read_bytes())
        self.assertEqual(hashlib.sha256((self.source / 'lib/libjemalloc-heaplens.so').read_bytes()).hexdigest(), EXPECTED)

    def test_segregation_with_jemalloc_global(self):
        result = self.run_probe(self.good, 'libjemalloc.so')
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_segregation_with_mimalloc_global(self):
        result = self.run_probe(self.good, 'libmimalloc.so')
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_reopening_global_jemalloc_is_rejected(self):
        result = self.run_probe(self.bad, 'libjemalloc.so')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('resolved to the process-wide allocator', result.stdout)

    def test_reopening_global_mimalloc_is_rejected(self):
        result = self.run_probe(self.mimalloc, 'libmimalloc.so')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('resolved to the process-wide allocator', result.stdout)
