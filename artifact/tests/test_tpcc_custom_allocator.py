"""Caller-level typing for the pinned TPC-C allocator, not arbitrary alloc methods."""
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
class TpccCustomAllocator(unittest.TestCase):
    def test_registered_allocator_and_unrelated_factories(self):
        base = Path(os.environ.get('HEAPLENS_TEST_EVIDENCE', tempfile.gettempdir()))
        base.mkdir(parents=True, exist_ok=True)
        trial = Path(tempfile.mkdtemp(prefix='tpcc-custom-', dir=base))
        source = trial/'input'
        source.mkdir()
        target = trial/'project'
        # Use the actual wrapper and allocator bodies, with only their unrelated
        # benchmark dependencies stubbed. Fail if the pinned allocation path changes.
        original = (ROOT/'artifact/vendor/setbench/macrobench/system/mem_alloc.cpp').read_text()
        uncommented = re.sub(r'//[^\n]*|/\*.*?\*/', '', original, flags=re.S)
        allocation = re.search(r'void\s*\*\s*mem_alloc::alloc\([^)]*\)\s*\{[^}]*\}', uncommented).group()
        self.assertEqual(re.sub(r'\s+', '', allocation.split('{', 1)[1]),
                         'void*ptr;ptr=malloc(size);returnptr;}')
        # free has one nested conditional; take its complete original definition.
        start = original.index('void mem_alloc::free(')
        end = original.index('\n}', start) + 2
        release = original[start:end]
        shutil.copy2(ROOT/'artifact/patches/setbench-tpcc/macrobench/system/mem_alloc.h',
                     source/'mem_alloc.h')
        (source/'global.h').write_text('#pragma once\n#include <cstdint>\n'
            '#include <cstdlib>\n#include <pthread.h>\nusing UInt32 = uint32_t;\n'
            'constexpr bool NO_FREE_B = false;\n')
        (source/'allocator.cpp').write_text('#include "mem_alloc.h"\n'+allocation+'\n'+release+'\n')
        # Negative cases include both a differently named class and an identically
        # named class in another namespace. Neither supplies a template wrapper.
        (source/'objects.h').write_text('''#pragma once
#include "mem_alloc.h"
struct Row_lock { char data[64]; };
struct LockEntry { char data[32]; };
struct FactoryNode { char data[24]; };
struct Factory { static FactoryNode* alloc() { return new FactoryNode; } };
namespace unrelated {
struct mem_alloc { static FactoryNode* alloc() { return new FactoryNode; } };
}
''')
        program = r'''#include "objects.h"
#include <cstdio>
int main() {
    mem_alloc allocator;
    Row_lock* rows[20]; LockEntry* locks[20]; uint64_t* ids[20];
    FactoryNode* factory[20]; FactoryNode* other[20];
    for (int i=0; i<20; ++i) {
        Row_lock* manager;
        manager = (Row_lock*)allocator.alloc(sizeof(Row_lock), i);
        LockEntry* entry = (LockEntry*)allocator.alloc(sizeof(LockEntry), i);
        uint64_t* id = (uint64_t*)allocator.alloc(sizeof(uint64_t), i);
        rows[i]=manager; locks[i]=entry; ids[i]=id;
        manager->data[63]=i; entry->data[31]=i; *id=i;
        factory[i]=Factory::alloc();
        other[i]=unrelated::mem_alloc::alloc();
        printf("EXPECT %p %zu Row_lock\n", (void*)manager, sizeof(*manager));
        printf("EXPECT %p %zu LockEntry\n", (void*)entry, sizeof(*entry));
        printf("EXPECT %p %zu uint64_t\n", (void*)id, sizeof(*id));
        printf("EXPECT %p %zu FactoryNode\n", (void*)factory[i], sizeof(*factory[i]));
        printf("EXPECT %p %zu FactoryNode\n", (void*)other[i], sizeof(*other[i]));
    }
    for (int i=0; i<20; ++i) {
        if (rows[i]->data[63]!=i || locks[i]->data[31]!=i || *ids[i]!=i) return 70;
        allocator.free(rows[i], sizeof(*rows[i]));
        allocator.free(locks[i], sizeof(*locks[i]));
        allocator.free(ids[i], sizeof(*ids[i]));
        delete factory[i]; delete other[i];
    }
}
'''
        (source/'probe.cpp').write_text(program)
        source_lines = {name: next(i for i, line in enumerate(program.splitlines(), 1)
                                  if 'allocator.alloc(sizeof('+name+')' in line)
                        for name in ('Row_lock', 'LockEntry', 'uint64_t')}
        (source/'Makefile').write_text('all:\n\tg++ -std=c++17 -O0 -pthread '
            '-I/root/sifter/memhook probe.cpp allocator.cpp -L/root/sifter/memhook '
            '-Wl,-rpath=/root/sifter/memhook -lmemhook -ldl -o probe\n')
        (trial/'driver.log').write_text(run(['bash', 'sifter.sh', str(source), str(target),
                                           '-t', '--skip-refactor']))
        run(['clang-apply-replacements-14', str(target)])
        run(['bash', 'sifter.sh', str(target), '--includes-only'])
        rewritten = (target/'probe.cpp').read_text()
        for name in ('Row_lock', 'LockEntry'):
            self.assertRegex(rewritten, r'allocator\.alloc<(?:struct )?'+name+r',\s*\d+,\s*\d+>')
        self.assertIn('Factory::alloc()', rewritten)
        self.assertIn('unrelated::mem_alloc::alloc()', rewritten)
        (trial/'build.log').write_text(run(['make'], target))
        output = run(['./probe'], target)
        (trial/'output.txt').write_text(output)
        expected = {int(addr, 16): (int(size), name) for addr, size, name in
                    re.findall(r'EXPECT (0x[0-9a-f]+) (\d+) (\w+)', output)}
        self.assertEqual(len(expected), 100)
        records = list(struct.iter_unpack('<QQQQHH?3x', (target/'binary_dump.txt').read_bytes()))
        types = {int(i): name for i, name in (line.split('|', 1) for line in
                 (target/'typeset_dump.txt').read_text().splitlines())}
        files = {int(i): name for i, name in (line.split('|', 1) for line in
                 (target/'fileset_dump.txt').read_text().splitlines())}
        for address, (size, name) in expected.items():
            allocs = [r for r in records if r[6] and r[3] == address]
            frees = [r for r in records if not r[6] and r[3] == address]
            self.assertEqual(len(allocs), 1, (hex(address), name, allocs))
            self.assertEqual(len(frees), 1, (hex(address), name, frees))
            record = allocs[0]
            self.assertEqual(record[2], size)
            if name == 'uint64_t':
                self.assertIn(types[record[5]], ('unsigned long', 'unsigned long long'))
            else:
                self.assertEqual(types[record[5]], name)
            self.assertLessEqual(record[1], frees[0][1])
            if name in source_lines:
                self.assertTrue(files[record[4]].endswith('/probe.cpp'))
                self.assertEqual(record[0], source_lines[name])
        (trial/'verification.json').write_text(json.dumps(dict(
            typed_custom_allocations=60, unrelated_factory_allocations=40,
            exact_once_frees=100, caller_metadata_checked=True,
            pinned_allocator_is_plain_malloc=True), indent=2)+'\n')


if __name__ == '__main__':
    unittest.main()
