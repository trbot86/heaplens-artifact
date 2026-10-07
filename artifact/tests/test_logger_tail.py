"""Fault injection into actual shared-library process-exit writes."""
import json,os,struct,subprocess,tempfile,unittest
from pathlib import Path
from test_project_header_logging import ROOT,run

@unittest.skipUnless(os.getenv('HEAPLENS_RUN_INSTRUMENTATION_TESTS')=='1','opt-in native library test')
class LoggerTail(unittest.TestCase):
    def test_short_interrupted_and_failed_final_writes(self):
        base=Path(os.environ.get('HEAPLENS_TEST_EVIDENCE',tempfile.gettempdir()))
        trial=Path(tempfile.mkdtemp(prefix='logger-tail-',dir=base))
        run(['make','clean'],ROOT/'memhook')
        (trial/'build.log').write_text(run(['make','USE_TEMPLATE=1'],ROOT/'memhook'))
        (trial/'probe.cpp').write_text(r'''
#include "memhook_interface.h"
#include <cstdlib>
#include <pthread.h>
struct TailObject { long values[8]; };
static void* worker(void*) {
  for(int i=0;i<13;++i) {
    void* p=malloc(sizeof(TailObject));
    memhook_record_alloc(p,sizeof(TailObject),typeid(TailObject),0,1);
    free(p);
  }
  return nullptr;
}
int main() {
  pthread_t threads[3];
  for(auto& t:threads) if(pthread_create(&t,nullptr,worker,nullptr))return 2;
  for(auto& t:threads) if(pthread_join(t,nullptr))return 3;
}
''')
        run(['g++','-std=c++11','-O0','-I'+str(ROOT/'memhook'),'probe.cpp','-L'+str(ROOT/'memhook'),
             '-Wl,-rpath='+str(ROOT/'memhook'),'-lmemhook','-ldl','-pthread','-o','probe'],trial)
        run(['g++','-std=c++11','-shared','-fPIC',str(ROOT/'artifact/tests/fixtures/logger_tail_fault.cpp'),'-ldl','-o','fault.so'],trial)
        outcomes=[]
        for fault in range(6):
            cell=trial/str(fault);cell.mkdir()
            env=os.environ.copy();env.update(LD_PRELOAD=str(trial/'fault.so'),HEAPLENS_TEST_TAIL_FAULT=str(fault))
            p=subprocess.run([str(trial/'probe')],cwd=cell,env=env,capture_output=True,text=True,timeout=20)
            (cell/'output.txt').write_text(p.stdout+p.stderr)
            self.assertEqual(p.returncode,0 if fault<4 else 94,p.stderr)
            if fault<4:
                types={int(i):s for i,s in (line.split('|',1) for line in (cell/'typeset_dump.txt').read_text().splitlines())}
                rows=list(struct.iter_unpack('<QQQQHH?3x',(cell/'binary_dump.txt').read_bytes()))
                objects=[r for r in rows if r[6] and types.get(r[5])=='TailObject']
                self.assertEqual(len(objects),39)
                self.assertTrue(all(r[2]==64 and r[3] for r in objects))
                self.assertEqual(sum(not r[6] and r[3] in {x[3] for x in objects} for r in rows),39)
            else:self.assertIn('trace invalid',p.stderr)
            outcomes.append(dict(fault=fault,returncode=p.returncode,trace_bytes=(cell/'binary_dump.txt').stat().st_size))
        for fault,variable in [('type-open','MEMHOOK_OUTPUT_TYPE_FILE'),
                               ('type-write','MEMHOOK_OUTPUT_TYPE_FILE'),
                               ('binary-open','MEMHOOK_OUTPUT_DUMP_FILE')]:
            cell=trial/fault;cell.mkdir();blocked=cell/'blocked';blocked.mkdir()
            env=os.environ.copy();env[variable]='/dev/full' if fault=='type-write' else str(blocked)
            p=subprocess.run([str(trial/'probe')],cwd=cell,env=env,capture_output=True,text=True,timeout=20)
            (cell/'output.txt').write_text(p.stdout+p.stderr)
            self.assertEqual(p.returncode,94,p.stderr)
            self.assertIn('trace invalid',p.stderr)
            outcomes.append(dict(fault=fault,returncode=p.returncode))
        (trial/'verification.json').write_text(json.dumps(dict(status='passed',outcomes=outcomes),indent=2))
