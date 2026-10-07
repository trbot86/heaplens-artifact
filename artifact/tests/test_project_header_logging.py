"""Native regression for the actual sifter.sh project-header rewrite paths.

Run in the artifact image with HEAPLENS_RUN_INSTRUMENTATION_TESTS=1. The driver
builds its own tools, so these tests are opt-in rather than ordinary unit tests.
"""
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def run(args, cwd=ROOT, env=None):
    p = subprocess.run(args, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, timeout=360)
    if p.returncode:
        raise AssertionError(str(args) + '\n' + p.stdout[-16000:])
    return p.stdout


@unittest.skipUnless(os.getenv('HEAPLENS_RUN_INSTRUMENTATION_TESTS') == '1',
                     'opt-in native toolchain test in the artifact image')
class ProjectHeaderLogging(unittest.TestCase):
    def exercise(self, export, unusual_path=False):
        # Retain the complete rewritten project and trace when a test fails.
        base = Path(os.environ.get('HEAPLENS_TEST_EVIDENCE', tempfile.gettempdir()))
        base.mkdir(parents=True, exist_ok=True)
        trial = Path(tempfile.mkdtemp(prefix='headers-', dir=base))
        source = trial/'input'
        target = trial/('project [a]+(b)' if unusual_path else 'project')
        (source/'include').mkdir(parents=True)
        (source/'build').mkdir()
        external = trial/'external.h'
        external.write_text('#pragma once\nstruct External { long value; };\n'
                            'inline External* external_new() { return new External; }\n')
        (source/'include/shared.h').write_text('''#pragma once
#include <cstdlib>
template<int K> struct HeaderNode { long value[K]; };
template<int K> inline HeaderNode<K>* header_new() { return new HeaderNode<K>; }
struct HeaderMalloc { long value[3]; };
inline HeaderMalloc* header_malloc() {
    HeaderMalloc* p = (HeaderMalloc*)malloc(sizeof(HeaderMalloc));
    return p;
}
HeaderNode<2>* from_other_unit();
''')
        (source/'build/other.cpp').write_text('#include "shared.h"\n'
            'HeaderNode<2>* from_other_unit() { return header_new<2>(); }\n')
        (source/'build/main.cpp').write_text('''#include "shared.h"
#include "EXTERNAL"
#include <cstdio>
struct MainNode { long value[4]; };
int main() {
    HeaderNode<1>* a[20]; HeaderNode<2>* b[20]; HeaderMalloc* c[20];
    MainNode* d[20]; External* e[20];
    for (int i=0; i<20; ++i) {
        a[i]=header_new<1>(); b[i]=from_other_unit(); c[i]=header_malloc();
        d[i]=new MainNode; e[i]=external_new();
        printf("EXPECT %p %zu header\\n", (void*)a[i], sizeof(*a[i]));
        printf("EXPECT %p %zu header\\n", (void*)b[i], sizeof(*b[i]));
        printf("EXPECT %p %zu header\\n", (void*)c[i], sizeof(*c[i]));
        printf("EXPECT %p %zu main\\n", (void*)d[i], sizeof(*d[i]));
    }
    for (int i=0; i<20; ++i) { delete a[i]; delete b[i]; free(c[i]); delete d[i]; delete e[i]; }
}
'''.replace('EXTERNAL', str(external)))
        (source/'build/Makefile').write_text('''all:
\tg++ -std=c++17 -O0 -I../include -I/root/sifter/memhook main.cpp other.cpp -L/root/sifter/memhook -Wl,-rpath=/root/sifter/memhook -lmemhook -ldl -pthread -o probe
''')
        external_before = external.read_bytes()
        args = ['bash', 'sifter.sh', str(source), str(target), '-t', '-s', 'build']
        if export:
            args += ['--skip-refactor']
        log = run(args)
        (trial/'driver.log').write_text(log)
        if export:
            (trial/'apply.log').write_text(run(['clang-apply-replacements-14', str(target)]))
            run(['bash', 'sifter.sh', str(target), '--includes-only'])
        self.assertEqual(external.read_bytes(), external_before)
        (trial/'build.log').write_text(run(['make'], target/'build'))
        output = run(['./probe'], target/'build')
        (trial/'output.txt').write_text(output)
        expected = {int(addr,16):(int(size),where) for addr,size,where in re.findall(
            r'EXPECT (0x[0-9a-f]+) (\d+) (\w+)', output)}
        self.assertEqual(len(expected),80)
        records = list(struct.iter_unpack('<QQQQHH?3x',(target/'build/binary_dump.txt').read_bytes()))
        types = {int(i):name for i,name in (s.split('|',1) for s in
                 (target/'build/typeset_dump.txt').read_text().splitlines())}
        files = {int(i):name for i,name in (s.split('|',1) for s in
                 (target/'build/fileset_dump.txt').read_text().splitlines())}
        counts = {'header':0, 'main':0}
        for addr,(size,where) in expected.items():
            allocs=[r for r in records if r[6] and r[3]==addr]
            frees=[r for r in records if not r[6] and r[3]==addr]
            if len(allocs)==1:
                counts[where]+=1
        (trial/'counts.json').write_text(json.dumps(counts,indent=2)+'\n')
        self.assertEqual(counts, {'header':60,'main':20}, str(trial))
        for addr,(size,where) in expected.items():
            allocs=[r for r in records if r[6] and r[3]==addr]
            frees=[r for r in records if not r[6] and r[3]==addr]
            self.assertEqual(len(allocs),1)
            self.assertEqual(len(frees),1)
            a=allocs[0]
            self.assertEqual(a[2],size)
            self.assertRegex(types.get(a[5],''), r'^(Header(Node|Malloc)|MainNode)')
            self.assertTrue(files[a[4]].endswith('shared.h' if where=='header' else 'main.cpp'))
            self.assertLessEqual(a[1],frees[0][1])

    def test_exported_project_headers(self):
        self.exercise(export=True)

    def test_direct_apply_with_spaces_and_regex_characters(self):
        self.exercise(export=False, unusual_path=True)


if __name__ == '__main__':
    unittest.main()
