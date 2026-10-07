"""Run source annotation before checking the explicit TPC-C node hooks."""
import json
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
import unittest

from test_project_header_logging import ROOT, run


@unittest.skipUnless(os.getenv('HEAPLENS_RUN_INSTRUMENTATION_TESTS') == '1',
                     'opt-in native toolchain test in the artifact image')
class TpccHeaderLogging(unittest.TestCase):
    def test_annotation_and_explicit_hooks_coexist(self):
        base = Path(os.environ.get('HEAPLENS_TEST_EVIDENCE', tempfile.gettempdir()))
        trial = Path(tempfile.mkdtemp(prefix='tpcc-headers-', dir=base))
        source = trial/'input'
        target = trial/'project'
        vendor = ROOT/'artifact/vendor/setbench'
        shutil.copytree(vendor/'common', source/'common')
        shutil.copy2(ROOT/'artifact/patches/setbench-tpcc/common/recordmgr/allocator_new.h',
                     source/'common/recordmgr/allocator_new.h')
        (source/'build').mkdir()
        node = (ROOT/'artifact/patches/setbench-tpcc/ds/bronson_pext_bst_occ/ccavl_impl.h').read_text()
        node = node[node.index('template <typename skey_t, typename sval_t>\nstruct node_t'):]
        node = node[:node.index('/** This is a special value')]
        (source/'build/node.h').write_text('#include <pthread.h>\nstruct itemid_t;\n'
            'typedef pthread_spinlock_t ptlock_t;\ntypedef unsigned long long version_t;\n'+node)
        (source/'build/probe.cpp').write_text(r'''
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
        printf("NODE %lu %p %zu\n", i, (void*)nodes[i], sizeof(TestNode));
    }
    for (unsigned long i=0; i<1000; ++i) {
        if (nodes[i]->key!=i) return 70;
        allocator.deallocate(0,nodes[i]);
    }
}
''')
        separate = ROOT/'artifact/vendor/heaplens-allocators/libjemalloc-heaplens.so'
        (source/'build/Makefile').write_text('''all:
\tg++ -std=c++17 -O2 -pthread -I../common/recordmgr -I../common -I/root/sifter/memhook $(EXTRA) probe.cpp -L/root/sifter/memhook -Wl,-rpath=/root/sifter/memhook -lmemhook -ldl -o probe
''')
        # Match the artifact: annotate an ordinary build, enable explicit trace
        # hooks only when compiling the transformed source for execution.
        (trial/'driver.log').write_text(run(['bash','sifter.sh',str(source),str(target),
                                           '-t','-s','build','--skip-refactor']))
        (trial/'apply.log').write_text(run(['clang-apply-replacements-14',str(target)]))
        run(['bash','sifter.sh',str(target),'--includes-only'])
        rewritten = (target/'common/recordmgr/allocator_new.h').read_text()
        self.assertIn('T* result = new T; // NOLINT(misc-allocation-logging)',rewritten)
        receipts = []
        for segregated in (False,True):
            with self.subTest(segregated=segregated):
                cell=trial/('segregated' if segregated else 'ordinary'); cell.mkdir()
                flags='-DHEAPLENS_TPCC_TRACE=1'
                if segregated:
                    flags += ' -DMEMHOOK_SEG_DS -DMEMHOOK_SEG_DS_LIB=\\"'+str(separate)+'\\"'
                (cell/'build.log').write_text(run(['make','EXTRA='+flags],target/'build'))
                env=dict(os.environ,GLIBC_TUNABLES='glibc.rtld.optional_static_tls=4194304',
                         LD_PRELOAD=str(ROOT/'memhook/libmemhook.so')+':'+str(vendor/'lib/libjemalloc.so'))
                output=run([str(target/'build/probe')],cell,env)
                (cell/'output.txt').write_text(output)
                expected={int(addr,16):int(size) for addr,size in re.findall(
                    r'^NODE \d+ (0x[0-9a-f]+) (\d+)$',output,re.M)}
                self.assertEqual(len(expected),1000)
                records=list(struct.iter_unpack('<QQQQHH?3x',(cell/'binary_dump.txt').read_bytes()))
                types={int(i):name for i,name in (s.split('|',1) for s in
                       (cell/'typeset_dump.txt').read_text().splitlines())}
                allocations=[r for r in records if r[6] and r[3] in expected]
                frees=[r for r in records if not r[6] and r[3] in expected]
                self.assertEqual(len(allocations),1000); self.assertEqual(len(frees),1000)
                self.assertEqual({r[3] for r in allocations},set(expected))
                self.assertEqual({r[3] for r in frees},set(expected))
                self.assertTrue(all(r[2]==expected[r[3]]==56 and r[4]==65004 and
                                    types[r[5]].startswith('node_t<') for r in allocations))
                starts={r[3]:r[1] for r in allocations}
                self.assertTrue(all(r[1]>=starts[r[3]] for r in frees))
                receipts.append(dict(segregated=segregated,allocations=1000,frees=1000,size=56))
        (trial/'verification.json').write_text(json.dumps(receipts,indent=2)+'\n')


if __name__ == '__main__':
    unittest.main()
