"""Force cross-thread address reuse before the allocator's free call returns."""
import json,os,struct,subprocess,tempfile,unittest
from pathlib import Path
from test_project_header_logging import ROOT,run

@unittest.skipUnless(os.getenv('HEAPLENS_RUN_INSTRUMENTATION_TESTS')=='1','opt-in native library test')
class RetirementOrder(unittest.TestCase):
    def test_free_is_recorded_before_allocator_publishes_address(self):
        base=Path(os.environ.get('HEAPLENS_TEST_EVIDENCE',tempfile.gettempdir()))
        trial=Path(tempfile.mkdtemp(prefix='retirement-order-',dir=base))
        run(['make','clean'],ROOT/'memhook')
        (trial/'build.log').write_text(run(['make','USE_TEMPLATE=1'],ROOT/'memhook'))
        (trial/'probe.cpp').write_text(r'''
#include "memhook_interface.h"
#include <atomic>
#include <pthread.h>
#include <sched.h>
extern void (*next_free)(void*);
static void (*underlying_free)(void*);
static void* target;
static int mode;
static std::atomic<bool> released{false},reused{false};
struct FirstLifetime { char bytes[8192]; };
struct SecondLifetime { char bytes[8192]; };
// An allocator may make storage available before returning to its caller.
// Delay that return until a second producer records a new object there.
// Keep the backing block reserved so no unrelated allocation can steal it.
static void controlled_free(void* p) {
  if(p!=target) { underlying_free(p); return; }
  released.store(true,std::memory_order_release);
  while(!reused.load(std::memory_order_acquire)) sched_yield();
}
static void* retire(void*) {
  if(mode==0) free(target);
  else if(mode==1) ::operator delete(target);
  else ::operator delete[](target);
  return nullptr;
}
static void* reuse(void*) {
  while(!released.load(std::memory_order_acquire)) sched_yield();
  memhook_record_alloc(target,sizeof(SecondLifetime),typeid(SecondLifetime),62000,2);
  reused.store(true,std::memory_order_release);
  return nullptr;
}
int main(int argc,char** argv) {
  mode=argc>1?atoi(argv[1]):0;
  target=mode==0 ? malloc(8192) : (mode==1 ? ::operator new(8192) : ::operator new[](8192));
  printf("TARGET %llu\n",(unsigned long long)target);
  memhook_record_alloc(target,sizeof(FirstLifetime),typeid(FirstLifetime),62000,1);
  underlying_free=next_free;next_free=controlled_free;
  pthread_t a,b;
  if(pthread_create(&a,nullptr,retire,nullptr)||pthread_create(&b,nullptr,reuse,nullptr))return 2;
  pthread_join(a,nullptr);pthread_join(b,nullptr);
  next_free=underlying_free;
  free(target);
  ::operator delete(nullptr);::operator delete[](nullptr);free(nullptr);
}
''')
        run(['g++','-std=c++11','-O0','-I'+str(ROOT/'memhook'),'probe.cpp','-L'+str(ROOT/'memhook'),
             '-Wl,-rpath='+str(ROOT/'memhook'),'-lmemhook','-ldl','-pthread','-o','probe'],trial)
        outcomes=[]
        for mode in range(3):
            cell=trial/str(mode);cell.mkdir()
            p=subprocess.run([str(trial/'probe'),str(mode)],cwd=cell,capture_output=True,text=True,timeout=20)
            (cell/'output.txt').write_text(p.stdout+p.stderr);self.assertEqual(p.returncode,0,p.stderr)
            address=int(next(line.split()[1] for line in p.stdout.splitlines() if line.startswith('TARGET ')))
            rows=list(struct.iter_unpack('<QQQQHH?3x',(cell/'binary_dump.txt').read_bytes()))
            events=sorted([r for r in rows if r[3]==address],key=lambda r:r[1])
            self.assertEqual([r[6] for r in events],[True,False,True,False],events)
            self.assertFalse(any(not r[6] and r[3]==0 for r in rows),'null delete must not emit a retirement')
            outcomes.append(dict(mode=mode,target=address,event_timestamps=[r[1] for r in events],sequence=[r[6] for r in events]))
        (trial/'verification.json').write_text(json.dumps(dict(status='passed',outcomes=outcomes),indent=2))
