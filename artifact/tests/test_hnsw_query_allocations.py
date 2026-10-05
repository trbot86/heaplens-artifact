"""Query-context overlay guards and native diagnostic coverage, not timings."""
import os
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'artifact'))
from lib import hnsw_query_allocations as overlay
from lib.hnsw_trace import annotate
from lib.valkey_trace import prepare_toolchain, replace_once


class QueryOverlay(unittest.TestCase):
    def test_reapplication_and_missing_anchors(self):
        source = (ROOT / 'memhook/memhook.cpp').read_text()
        patched = overlay.logger(source)
        self.assertEqual(patched.count('void* mem = hl_hnsw_new(size);'), 2)
        with self.assertRaises(ValueError):
            overlay.logger(patched)
        with self.assertRaises(ValueError):
            overlay.logger('wrong source')
        hooks = overlay.hooks('')
        with self.assertRaises(ValueError):
            overlay.hooks(hooks)
        source = (ROOT / 'artifact/vendor/hnswlib-corrected/hnswlib/hnswalg.h').read_text()
        with self.assertRaises(ValueError):
            overlay.algorithm(overlay.algorithm(source))

    @unittest.skipUnless(sys.platform.startswith('linux') and shutil.which('g++'),
                         'requires Linux and g++')
    def test_native_both_layouts(self):
        with tempfile.TemporaryDirectory(prefix='heaplens-hnsw-query-') as tmp:
            out = Path(tmp)
            tool = prepare_toolchain(ROOT, out)
            logger = tool / 'memhook/memhook.cpp'
            logger.write_text(overlay.logger(logger.read_text()))
            subprocess.run(['make', 'USE_TEMPLATE=1', '-j2'], cwd=tool/'memhook',
                           check=True, timeout=120, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            work = out / 'source'
            shutil.copytree(ROOT/'artifact/vendor/hnswlib-corrected', work,
                            ignore=shutil.ignore_patterns('.git', 'build*', '__pycache__'))
            hooks = work/'hnswlib/heaplens_hooks.h'
            shutil.copy2(ROOT/'artifact/lib/hnsw_trace/heaplens_hooks.h', hooks)
            replace_once(hooks, '#include "memhook_interface.h"',
                '#include "memhook_interface.h"\nextern "C" void memhook_record_alloc(void*,size_t,int,uint16_t,uint16_t);\n#define MEMHOOK_LOG_CPP_ALLOC_AT(ptr, sz, tid, fid, ln) memhook_record_alloc(ptr,sz,ln,fid,typetable.insert(&tid));')
            hooks.write_text(overlay.hooks(hooks.read_text()))
            annotate(work)
            algorithm = work/'hnswlib/hnswalg.h'
            algorithm.write_text(overlay.algorithm(algorithm.read_text()))
            for optimized in (False, True):
                binary = out / ('optimized' if optimized else 'baseline')
                defines = ['-DHNSWLIB_LAYOUT_VECTOR_SOA64=1', '-DHNSWLIB_LAYOUT_MADVISE_HUGEPAGE=1'] if optimized else []
                subprocess.run(['g++', '-O2', '-std=c++17', '-pthread', '-DHEAPLENS_ENABLE',
                    *defines, '-I'+str(work), '-I'+str(tool/'memhook'),
                    str(ROOT/'artifact/lib/hnsw_trace/heaplens_hnsw_bench.cpp'),
                    '-L'+str(tool/'memhook'), '-Wl,-rpath='+str(tool/'memhook'),
                    '-lmemhook', '-ldl', '-o', str(binary)], check=True, timeout=120,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                trial = out / (binary.name+'-output'); trial.mkdir()
                env = dict(os.environ, MEMHOOK_OUTPUT_DUMP_FILE=str(trial/'events.bin'),
                           MEMHOOK_OUTPUT_TYPE_FILE=str(trial/'types.txt'))
                subprocess.run([str(binary), '--elements', '2000', '--dim', '128',
                    '--queries', '100', '--iterations', '1', '--warmup', '10',
                    '--threads', '2', '--build-threads', '2', '--m', '16',
                    '--ef-construction', '200', '--ef-search', '64', '--k', '10',
                    '--query-mode', 'indexed', '--seed', '47'], cwd=trial, env=env,
                    check=True, timeout=120, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertIn('HeapLensHnswQueryScratch', (trial/'types.txt').read_text())
                self.assertGreater((trial/'events.bin').stat().st_size, 0)
                self.assertEqual((trial/'events.bin').stat().st_size % 40, 0)
                type_ids = {int(line.split('|', 1)[0]) for line in
                            (trial/'types.txt').read_text().splitlines()
                            if 'HeapLensHnswQueryScratch' in line}
                records = struct.iter_unpack('<QQQQHH?3x', (trial/'events.bin').read_bytes())
                scratch = [r for r in records if r[5] in type_ids and r[6]]
                self.assertTrue(scratch, 'No typed query scratch allocation records')
                self.assertTrue(all(r[2] > 0 and r[3] != 0 and r[4] == 65001 for r in scratch))


if __name__ == '__main__':
    unittest.main()
