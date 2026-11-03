"""Native pinned RocksDB header paths, including the existing ISL region hook.

This is a small correctness probe, not db_bench or a performance measurement.
The test allocator reports backing addresses independently of the trace.
"""
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
class RocksdbHeaderLogging(unittest.TestCase):
    def test_skiplist_nodes_and_inline_regions(self):
        base=Path(os.environ.get('HEAPLENS_TEST_EVIDENCE',tempfile.gettempdir()))
        trial=Path(tempfile.mkdtemp(prefix='rocksdb-headers-',dir=base))
        source=trial/'input'; target=trial/'project'
        shutil.copytree(ROOT/'artifact/vendor/rocksdb',source,
                        ignore=shutil.ignore_patterns('.git','*.o','*.a','*.so'))
        (source/'probe.cpp').write_text(r'''
#include <cstdio>
#include <cstring>
#include "memtable/skiplist.h"
#include "memtable/inlineskiplist.h"
using namespace rocksdb;
class ProbeAllocator : public Allocator {
    const char* label; void* pointers[128]; unsigned count=0;
public:
    explicit ProbeAllocator(const char* name) : label(name) {}
    ~ProbeAllocator() { for (unsigned i=0;i<count;++i) free(pointers[i]); }
    char* Allocate(size_t n) override { return AllocateAligned(n); }
    char* AllocateAligned(size_t n,size_t=0,Logger* =nullptr) override {
        void* p=malloc(n); // NOLINT(misc-allocation-logging)
        if (!p || count==128) abort();
        printf("ARENA %s %u %p %zu\n",label,count,p,n);
        pointers[count++]=p; return static_cast<char*>(p);
    }
    size_t BlockSize() const override { return 4096; }
};
struct IntegerComparator {
    int operator()(uint64_t a,uint64_t b) const { return (a>b)-(a<b); }
};
struct ByteComparator {
    using DecodedType=uint64_t;
    uint64_t decode_key(const char* p) const { uint64_t x; memcpy(&x,p,8); return x; }
    int operator()(const char* a,uint64_t y) const {
        uint64_t x=decode_key(a); return (x>y)-(x<y);
    }
    int operator()(const char* a,const char* b) const {
        return operator()(a,decode_key(b));
    }
};
int main() {
    static_assert(sizeof(void*)==8,"64-bit layout probe");
    ProbeAllocator h("hsl"), i("isl");
    SkipList<uint64_t,IntegerComparator> hsl(IntegerComparator{},&h);
    InlineSkipList<ByteComparator> isl(ByteComparator{},&i);
    Random::GetTLSInstance()->Reset(301);
    for(uint64_t k=1;k<=30;++k) {
        hsl.Insert(k);
        char* key=isl.AllocateKey(8); memcpy(key,&k,8);
        printf("KEY %p\n",static_cast<void*>(key));
        if (!isl.Insert(key)) return 70;
    }
    for(uint64_t k=1;k<=30;++k) {
        if (!hsl.Contains(k) || !isl.Contains(reinterpret_cast<const char*>(&k))) return 71;
    }
}
''')
        (source/'Makefile').write_text('''all:
\tg++ -std=c++17 -O0 -pthread -DNDEBUG -DOS_LINUX -DROCKSDB_PLATFORM_POSIX -I. -Iinclude -I/root/sifter/memhook probe.cpp util/random.cc -L/root/sifter/memhook -Wl,-rpath=/root/sifter/memhook -lmemhook -ldl -o header_probe
''')
        (trial/'driver.log').write_text(run(['bash','sifter.sh',str(source),str(target),
                                           '-t','--skip-refactor']))
        lib=ROOT/'artifact/lib'
        # Same post-annotation sequence used by rocksdb_experiment.sh.
        run(['python3',str(lib/'dedupe_fixes_yaml.py'),str(target/'fixes.yaml')])
        run(['clang-apply-replacements-14',str(target)])
        for script in ('fixup_anon_namespace_casts.py','fixup_malformed_insertions.py'):
            run(['python3',str(lib/script),str(target)])
        run(['bash','sifter.sh',str(target),'--includes-only'])
        run(['python3',str(lib/'patch_allocate_overloads.py'),str(target)])
        run(['python3',str(lib/'rocksdb_inline_regions.py'),str(target)])
        (trial/'build.log').write_text(run(['make'],target))
        output=run(['./header_probe'],target)
        (trial/'output.txt').write_text(output)
        arenas={'hsl':[], 'isl':[]}
        for name,index,addr,size in re.findall(r'ARENA (\w+) (\d+) (0x[0-9a-f]+) (\d+)',output):
            self.assertEqual(int(index),len(arenas[name]))
            arenas[name].append((int(addr,16),int(size)))
        self.assertEqual({name:len(rows) for name,rows in arenas.items()},{'hsl':32,'isl':32})
        records=list(struct.iter_unpack('<QQQQHH?3x',(target/'binary_dump.txt').read_bytes()))
        types={int(i):name for i,name in (s.split('|',1) for s in
               (target/'typeset_dump.txt').read_text().splitlines())}
        files={int(i):name for i,name in (s.split('|',1) for s in
               (target/'fileset_dump.txt').read_text().splitlines())}
        hsl=[r for r in records if r[6] and types.get(r[5],'').startswith('rocksdb::SkipList<')
             and types[r[5]].endswith('::Node')]
        isl=[r for r in records if r[6] and types.get(r[5],'').startswith('rocksdb::InlineSkipList<')
             and types[r[5]].endswith('::Node')]
        prefixes=[r for r in records if r[6] and types.get(r[5],'').startswith('std::atomic<rocksdb::InlineSkipList<')]
        self.assertEqual(len(hsl),31); self.assertEqual(len(isl),31)
        self.assertEqual({r[3] for r in hsl},{p for j,(p,n) in enumerate(arenas['hsl']) if j!=1})
        self.assertTrue(all(r[2]==16 and files[r[4]].endswith('memtable/skiplist.h') for r in hsl))
        # The public API returns the inline key immediately after its 8-byte node.
        keys=[int(p,16) for p in re.findall(r'KEY (0x[0-9a-f]+)',output)]
        expected=[(arenas['isl'][0][0]+arenas['isl'][0][1]-8,8)]+[(p-8,16) for p in keys]
        self.assertEqual({(r[3],r[2]) for r in isl},set(expected))
        expected_prefixes={(raw,node-raw) for (raw,_),(node,_) in
                           zip([arenas['isl'][0]]+arenas['isl'][2:],expected) if node>raw}
        self.assertEqual(len(prefixes),len(expected_prefixes))
        self.assertEqual({(r[3],r[2]) for r in prefixes},expected_prefixes)
        self.assertTrue(all(files[r[4]].endswith('memtable/inlineskiplist.h') for r in isl+prefixes))
        (trial/'verification.json').write_text(json.dumps(dict(hsl_nodes=len(hsl),
            isl_nodes=len(isl),isl_prefixes=len(prefixes),successful_lookups=60),indent=2)+'\n')


if __name__ == '__main__':
    unittest.main()
