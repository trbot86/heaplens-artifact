"""Test the actual generated RocksDB allocator adapter, including cleanup."""
from collections import Counter
import json,os,re,struct,tempfile,unittest
from pathlib import Path
from test_project_header_logging import ROOT,run

@unittest.skipUnless(os.getenv('HEAPLENS_RUN_INSTRUMENTATION_TESTS')=='1','opt-in native toolchain')
class CustomAllocatorLogging(unittest.TestCase):
    def test_pinned_adapter_preserves_custom_new_and_failed_constructor_cleanup(self):
        base=Path(os.environ.get('HEAPLENS_TEST_EVIDENCE',tempfile.gettempdir()))
        trial=Path(tempfile.mkdtemp(prefix='custom-allocator-',dir=base))
        source=trial/'input'; (source/'monitoring').mkdir(parents=True); target=trial/'project'
        header=source/'monitoring/statistics_impl.h'
        helper=ROOT/'artifact/lib/rocksdb_statistics_logging.py'
        for vendor in ('rocksdb','rocksdb-historical'):
            header.write_bytes((ROOT/'artifact/vendor'/vendor/'monitoring/statistics_impl.h').read_bytes())
            run(['python3',str(helper),str(source)])
            saved=trial/(vendor+'-adapter.h'); saved.write_bytes(header.read_bytes())
        text=header.read_text()
        prelude=text[text.index('// HeapLENS explicit StatisticsData allocation adapter'):text.index('namespace ROCKSDB_NAMESPACE {')]
        start=text.index('    HEAPLENS_STATISTICS_ALLOCATION void* operator new')
        methods=text[start:text.index('\n  };',start)]
        # Compile the exact generated methods with a small aligned object and
        # allocator that independently prints its actual returned extent.
        cpp=r'''
#include <new>
#include <cstdio>
#include <cstdlib>
#include <cstddef>
PRELUDE
static bool fail_construction=false;
namespace rocksdb {
namespace port {
void* cacheline_aligned_alloc(size_t s) {
  void* p=nullptr;
  if(posix_memalign(&p,64,s)) throw std::bad_alloc(); // NOLINT(misc-allocation-logging)
  printf("EXPECT rocksdb::StatisticsData %p %zu\n",p,s); return p;
}
void cacheline_aligned_free(void* p) { printf("CUSTOM_FREE %p\n",p); free(p); }
}
struct alignas(64) StatisticsData {
  long fields[8];
  StatisticsData() { if(fail_construction) throw 7; }
  ~StatisticsData() {}
METHODS
};
struct Plain { long fields[8]; ~Plain() {} };
template<class T> T* array(int n) { return new T[n]; }
}
int main() {
  auto* one=new rocksdb::StatisticsData;
  auto* many=rocksdb::array<rocksdb::StatisticsData>(2);
  auto* plain=rocksdb::array<rocksdb::Plain>(2);
  if((size_t)one%64 || (size_t)many%64) return 3;
  printf("EXPECT rocksdb::Plain %p %zu\n",(char*)plain-sizeof(size_t),2*sizeof(*plain)+sizeof(size_t));
  delete one; delete[] many;
  fail_construction=true;
  try { new rocksdb::StatisticsData; return 4; } catch(int n) { if(n!=7) return 5; }
  try { rocksdb::array<rocksdb::StatisticsData>(3); return 6; } catch(int n) { if(n!=7) return 7; }
  // Retain this ordinary allocation until the exception runtime has finished;
  // otherwise its unannotated exception storage can reuse the same address.
  delete[] plain;
}
'''.replace('PRELUDE',prelude).replace('METHODS',methods)
        (source/'main.cpp').write_text(cpp)
        flags=' -I/root/sifter/memhook main.cpp -L/root/sifter/memhook -Wl,-rpath=/root/sifter/memhook -lmemhook -ldl -pthread -o probe'
        (source/'Makefile').write_text('all:\n\tg++ -std=c++17 -O0'+flags+'\n')
        # The uninstrumented reference must not depend on a logger left by an
        # earlier test. sifter.sh builds the logger for the instrumented copy.
        before=run(['g++','-std=c++17','-O0','main.cpp','-pthread','-o','probe'],source)
        (trial/'original-build.log').write_text(before)
        original=run([str(source/'probe')],source); (trial/'original-output.txt').write_text(original)
        original_sizes=Counter((t,int(n)) for t,p,n in re.findall(r'EXPECT (\S+) (0x[0-9a-f]+) (\d+)',original))
        (trial/'driver.log').write_text(run(['bash','sifter.sh',str(source),str(target),'-t','--skip-refactor']))
        run(['clang-apply-replacements-14',str(target)])
        run(['bash','sifter.sh',str(target),'--includes-only'])
        for standard in ('c++11','c++17'):
            cell=trial/standard;cell.mkdir()
            (cell/'build.log').write_text(run(['g++','-std='+standard,'-O2',*flags.split()],target))
            output=run([str(target/'probe')],cell); (cell/'output.txt').write_text(output)
            expected=[(t,int(p,16),int(n)) for t,p,n in re.findall(r'EXPECT (\S+) (0x[0-9a-f]+) (\d+)',output)]
            self.assertEqual(len(expected),5)
            self.assertEqual(Counter((t,n) for t,p,n in expected),original_sizes)
            self.assertEqual(len(re.findall('CUSTOM_FREE',output)),4)
            rows=sorted(struct.iter_unpack('<QQQQHH?3x',(cell/'binary_dump.txt').read_bytes()),key=lambda r:r[1])
            types={int(i):s for i,s in (line.split('|',1) for line in (cell/'typeset_dump.txt').read_text().splitlines())}
            names={t for t,p,n in expected}
            actual=[(types.get(r[5]),r[3],r[2]) for r in rows if r[6] and types.get(r[5]) in names]
            self.assertEqual(Counter(actual),Counter(expected))
            for i,r in enumerate(rows):
                if not r[6] or types.get(r[5]) not in names:continue
                end=next((j for j in range(i+1,len(rows)) if rows[j][6] and rows[j][3]==r[3]),len(rows))
                self.assertEqual(sum(not x[6] and x[3]==r[3] for x in rows[i+1:end]),1)
            (cell/'verification.json').write_text(json.dumps(dict(status='passed',expected=expected,actual=actual,custom_cleanups=4),indent=2))
