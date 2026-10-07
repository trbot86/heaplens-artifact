"""Native node lifetimes for both allocators; plain builds stay logger-free."""
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT/'artifact/vendor/setbench'


def run(cmd, cwd, env=None):
    result = subprocess.run(cmd, cwd=cwd, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    if result.returncode:
        raise AssertionError(str(cmd) + '\n' + result.stdout[-12000:])
    return result.stdout


@unittest.skipUnless(sys.platform.startswith('linux') and shutil.which('g++'), 'requires Linux and g++')
class NodeRecords(unittest.TestCase):
    def test_exact_records_and_plain_controls(self):
        self.assertTrue((VENDOR/'common/recordmgr/globals.h').exists(), 'initialize SetBench submodule')
        with tempfile.TemporaryDirectory(prefix='heaplens-tpcc-records-') as tmp:
            tmp = Path(tmp)
            logger = tmp/'memhook'
            shutil.copytree(ROOT/'memhook', logger, ignore=shutil.ignore_patterns('*.o', '*.so'))
            run(['make', 'USE_TEMPLATE=1', '-j2'], logger)
            node = (ROOT/'artifact/patches/setbench-tpcc/ds/bronson_pext_bst_occ/ccavl_impl.h').read_text()
            node = node[node.index('template <typename skey_t, typename sval_t>\nstruct node_t'):]
            node = node[:node.index('/** This is a special value')]
            (tmp/'node.h').write_text('#include <pthread.h>\nstruct itemid_t;\n'
                'typedef pthread_spinlock_t ptlock_t;\ntypedef unsigned long long version_t;\n' + node)
            (tmp/'probe.cpp').write_text(r'''
#include <cassert>
#include <cstdio>
#include "globals.h"
#include "allocator_new.h"
#include "node.h"
using TestNode = node_t<unsigned long, itemid_t*>;
static TestNode* nodes[1000];
int main() {
    debugInfo debug(1);
    allocator_new<TestNode> allocator(1, &debug);
    for (unsigned long i=0; i<1000; ++i) {
        nodes[i]=allocator.allocate(0); nodes[i]->key=i;
        printf("NODE %lu %p %zu\n",i,(void*)nodes[i],sizeof(TestNode));
    }
    for (unsigned long i=0; i<1000; ++i) {
        if (nodes[i]->key!=i) return 70;
        allocator.deallocate(0,nodes[i]);
    }
}
''')
            global_allocator = VENDOR/'lib/libjemalloc.so'
            separate = ROOT/'artifact/vendor/heaplens-allocators/libjemalloc-heaplens.so'
            for traced in (False, True):
                for segregated in (False, True):
                    with self.subTest(traced=traced, segregated=segregated):
                        trial=tmp/f'{traced}-{segregated}'; trial.mkdir()
                        flags=['-std=c++17', '-O2', '-pthread', '-I'+str(tmp),
                               '-I'+str(ROOT/'artifact/patches/setbench-tpcc/common/recordmgr'),
                               '-I'+str(VENDOR/'common/recordmgr'), '-I'+str(VENDOR/'common')]
                        if segregated:
                            flags += ['-DMEMHOOK_SEG_DS', '-DMEMHOOK_SEG_DS_LIB="'+str(separate)+'"']
                        if traced:
                            flags += ['-DHEAPLENS_TPCC_TRACE=1', '-I'+str(logger), '-L'+str(logger),
                                      '-Wl,-rpath='+str(logger)]
                        binary=trial/'probe'
                        run(['g++', *flags, str(tmp/'probe.cpp'), *(['-lmemhook'] if traced else []),
                             '-ldl', '-o', str(binary)], trial)
                        env=dict(os.environ, GLIBC_TUNABLES='glibc.rtld.optional_static_tls=4194304',
                                 LD_PRELOAD=(str(logger/'libmemhook.so')+':' if traced else '')+str(global_allocator))
                        output=run([str(binary)], trial, env)
                        expected={int(addr,16):int(size) for addr,size in re.findall(
                            r'^NODE \d+ (0x[0-9a-f]+) (\d+)$',output,re.M)}
                        self.assertEqual(len(expected),1000)
                        if not traced:
                            self.assertFalse((trial/'binary_dump.txt').exists())
                            self.assertNotIn('memhook',run(['nm','-u',str(binary)],trial))
                            continue
                        types={int(a):b for a,b in (line.split('|',1) for line in
                               (trial/'typeset_dump.txt').read_text().splitlines())}
                        records=list(struct.iter_unpack('<QQQQHH?3x',(trial/'binary_dump.txt').read_bytes()))
                        allocs=[r for r in records if r[6] and r[3] in expected]
                        frees=[r for r in records if not r[6] and r[3] in expected]
                        self.assertEqual(len(allocs),1000); self.assertEqual(len(frees),1000)
                        self.assertEqual({r[3] for r in allocs},set(expected))
                        self.assertEqual({r[3] for r in frees},set(expected))
                        self.assertTrue(all(types.get(r[5],'').startswith('node_t<') and
                                            r[2]==expected[r[3]]==56 and r[4]==65004 for r in allocs))
                        starts={r[3]:r[1] for r in allocs}
                        self.assertTrue(all(r[1]>=starts[r[3]] for r in frees))


if __name__ == '__main__':
    unittest.main()
