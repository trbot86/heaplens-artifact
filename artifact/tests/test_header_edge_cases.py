"""Native C and placement-new regressions for project-header annotation."""
import json
import os
from pathlib import Path
import re
import struct
import tempfile
import unittest

from test_project_header_logging import ROOT, run


@unittest.skipUnless(os.getenv('HEAPLENS_RUN_INSTRUMENTATION_TESTS') == '1',
                     'opt-in native toolchain test')
class HeaderEdgeCases(unittest.TestCase):
    def exercise(self, cpp):
        base=Path(os.environ.get('HEAPLENS_TEST_EVIDENCE',tempfile.gettempdir()))
        trial=Path(tempfile.mkdtemp(prefix='placement-' if cpp else 'c-header-',dir=base))
        source=trial/'input'; source.mkdir(); target=trial/'project'
        if cpp:
            (source/'shared.h').write_text('''#pragma once
#include <new>
namespace objects {
template<int K> struct Node { long values[K]; };
template<int K> struct Pool {
    using value_type=Node<K>;
    static value_type* construct(void* memory) { return new(memory) value_type(); }
};
Node<3>* construct_large(void* memory);
}
''')
            (source/'other.cpp').write_text('#include "shared.h"\n'
                'objects::Node<3>* objects::construct_large(void* memory) { return Pool<3>::construct(memory); }\n')
            (source/'main.cpp').write_text(r'''
#include "shared.h"
#include <cstdio>
int main() {
    alignas(objects::Node<1>) unsigned char small[20][sizeof(objects::Node<1>)];
    alignas(objects::Node<3>) unsigned char large[20][sizeof(objects::Node<3>)];
    for(int i=0;i<20;++i) {
        auto* a=objects::Pool<1>::construct(small[i]);
        auto* b=objects::construct_large(large[i]);
        a->values[0]=i; b->values[2]=i;
        printf("EXPECT %p %zu\n",(void*)a,sizeof(*a));
        printf("EXPECT %p %zu\n",(void*)b,sizeof(*b));
    }
}
''')
            compiler='g++ -std=c++17'; unit='main.cpp other.cpp'
        else:
            (source/'shared.h').write_text('''#pragma once
#include <stdlib.h>
typedef struct CNode { long values[3]; } CNode;
static inline CNode* header_alloc(void) {
    CNode* p=(CNode*)malloc(sizeof(CNode));
    return p;
}
''')
            (source/'main.c').write_text(r'''
#include "shared.h"
#include <stdio.h>
int main(void) {
    CNode* nodes[40];
    for(int i=0;i<20;++i) {
        nodes[i]=header_alloc();
        CNode* other=(CNode*)calloc(1,sizeof(CNode));
        nodes[i+20]=other;
    }
    for(int i=0;i<40;++i) printf("EXPECT %p %zu\n",(void*)nodes[i],sizeof(*nodes[i]));
    for(int i=0;i<40;++i) free(nodes[i]);
}
''')
            compiler='gcc -std=c11'; unit='main.c'
        (source/'Makefile').write_text('all:\n\t'+compiler+' -O0 -I/root/sifter/memhook '+unit+
            ' -L/root/sifter/memhook -Wl,-rpath=/root/sifter/memhook -lmemhook -ldl -pthread -o probe\n')
        # A previous test may have built the logger in the other language mode.
        (trial/'clean.log').write_text(run(['make','clean'],ROOT/'memhook'))
        (trial/'driver.log').write_text(run(['bash','sifter.sh',str(source),str(target),
                                           *(['-t'] if cpp else []),'--skip-refactor']))
        run(['clang-apply-replacements-14',str(target)])
        run(['bash','sifter.sh',str(target),'--includes-only'])
        (trial/'build.log').write_text(run(['make'],target))
        output=run(['./probe'],target); (trial/'output.txt').write_text(output)
        expected={int(p,16):int(n) for p,n in re.findall(r'EXPECT (0x[0-9a-f]+) (\d+)',output)}
        self.assertEqual(len(expected),40)
        records=list(struct.iter_unpack('<QQQQHH?3x',(target/'binary_dump.txt').read_bytes()))
        types={int(i):s for i,s in (row.split('|',1) for row in (target/'typeset_dump.txt').read_text().splitlines())}
        for p,size in expected.items():
            allocations=[r for r in records if r[6] and r[3]==p]
            self.assertEqual(len(allocations),1)
            self.assertEqual(allocations[0][2],size)
            self.assertIn('Node',types[allocations[0][5]])
            if not cpp:
                self.assertEqual(sum(not r[6] and r[3]==p for r in records),1)
        (trial/'verification.json').write_text(json.dumps(dict(allocations=40,
            frees=None if cpp else 40,requested_sizes=sorted(set(expected.values()))),indent=2)+'\n')

    def test_c_header_and_source(self):
        self.exercise(False)

    def test_template_placement_new(self):
        self.exercise(True)

    def test_factory_named_alloc_and_qualified_malloc(self):
        base=Path(os.environ.get('HEAPLENS_TEST_EVIDENCE',tempfile.gettempdir()))
        trial=Path(tempfile.mkdtemp(prefix='qualified-alloc-',dir=base))
        source=trial/'input'; source.mkdir(); target=trial/'project'
        (source/'shared.h').write_text('''#pragma once
#include <cstdlib>
namespace outside { struct Node { long value[3]; }; }
struct Factory {
    static outside::Node* alloc() { return new outside::Node; }
};
inline outside::Node* from_malloc() {
    outside::Node* p=(outside::Node*)::malloc(sizeof(outside::Node));
    return p;
}
''')
        (source/'main.cpp').write_text('''#include "shared.h"
#include <cstdio>
int main() {
    for(int i=0;i<20;++i) {
        outside::Node* a=Factory::alloc();
        outside::Node* b=from_malloc();
        printf("EXPECT %p\\n",(void*)a); printf("EXPECT %p\\n",(void*)b);
    }
}
''')
        (source/'Makefile').write_text('all:\n\tg++ -std=c++17 -O0 -I/root/sifter/memhook main.cpp '
            '-L/root/sifter/memhook -Wl,-rpath=/root/sifter/memhook -lmemhook -ldl -pthread -o probe\n')
        (trial/'clean.log').write_text(run(['make','clean'],ROOT/'memhook'))
        (trial/'driver.log').write_text(run(['bash','sifter.sh',str(source),str(target),'-t','--skip-refactor']))
        run(['clang-apply-replacements-14',str(target)])
        run(['bash','sifter.sh',str(target),'--includes-only'])
        self.assertIn('Factory::alloc()', (target/'main.cpp').read_text())
        (trial/'build.log').write_text(run(['make'],target))
        output=run(['./probe'],target); (trial/'output.txt').write_text(output)
        expected={int(p,16) for p in re.findall(r'EXPECT (0x[0-9a-f]+)',output)}
        self.assertEqual(len(expected),40)
        records=list(struct.iter_unpack('<QQQQHH?3x',(target/'binary_dump.txt').read_bytes()))
        types={int(i):s for i,s in (row.split('|',1) for row in (target/'typeset_dump.txt').read_text().splitlines())}
        for p in expected:
            allocations=[r for r in records if r[6] and r[3]==p]
            self.assertEqual(len(allocations),1)
            self.assertEqual(allocations[0][2],24)
            self.assertEqual(types[allocations[0][5]],'outside::Node')
        (trial/'verification.json').write_text(json.dumps(dict(allocations=40,
            requested_size=24,type='outside::Node'),indent=2)+'\n')

    def test_nested_template_malloc_across_translation_units(self):
        base=Path(os.environ.get('HEAPLENS_TEST_EVIDENCE',tempfile.gettempdir()))
        trial=Path(tempfile.mkdtemp(prefix='template-malloc-',dir=base))
        source=trial/'input'; source.mkdir(); target=trial/'project'
        (source/'shared.h').write_text('''#pragma once
#include <cstdlib>
namespace objects {
template<int K> struct Pool {
    struct Node { long values[K]; };
    Node** previous;
    Node* make() { Node* p=(Node*)malloc(sizeof(Node)); return p; }
    void init() { previous=(Node**)malloc(2*sizeof(Node*)); }
};
void other();
}
''')
        body='''
#include "shared.h"
#include <cstdio>
void exercise() {
    objects::Pool<SIZE> pool;
    pool.init(); printf("EXPECT %p %zu\\n",(void*)pool.previous,2*sizeof(void*));
    for(int i=0;i<20;++i) {
        auto* p=pool.make(); p->values[SIZE-1]=i;
        printf("EXPECT %p %zu\\n",(void*)p,sizeof(*p));
    }
}
'''
        (source/'main.cpp').write_text(body.replace('SIZE','1').replace('void exercise()','void small()')+
            '\nint main() { small(); objects::other(); }\n')
        (source/'other.cpp').write_text(body.replace('SIZE','3').replace('void exercise()','void objects::other()'))
        (source/'Makefile').write_text('all:\n\tg++ -std=c++17 -O0 -I/root/sifter/memhook main.cpp other.cpp '
            '-L/root/sifter/memhook -Wl,-rpath=/root/sifter/memhook -lmemhook -ldl -pthread -o probe\n')
        (trial/'clean.log').write_text(run(['make','clean'],ROOT/'memhook'))
        (trial/'driver.log').write_text(run(['bash','sifter.sh',str(source),str(target),'-t','--skip-refactor']))
        run(['clang-apply-replacements-14',str(target)])
        run(['bash','sifter.sh',str(target),'--includes-only'])
        (trial/'build.log').write_text(run(['make'],target))
        output=run(['./probe'],target); (trial/'output.txt').write_text(output)
        expected={int(p,16):int(n) for p,n in re.findall(r'EXPECT (0x[0-9a-f]+) (\d+)',output)}
        self.assertEqual(len(expected),42)
        records=list(struct.iter_unpack('<QQQQHH?3x',(target/'binary_dump.txt').read_bytes()))
        types={int(i):s for i,s in (row.split('|',1) for row in (target/'typeset_dump.txt').read_text().splitlines())}
        for p,size in expected.items():
            allocations=[r for r in records if r[6] and r[3]==p]
            self.assertEqual(len(allocations),1)
            self.assertEqual(allocations[0][2],size)
            self.assertIn('Node',types[allocations[0][5]])
        (trial/'verification.json').write_text(json.dumps(dict(allocations=42,
            requested_sizes=sorted(set(expected.values()))),indent=2)+'\n')
