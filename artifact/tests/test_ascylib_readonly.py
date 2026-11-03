"""Force the rare RNG boundary through ASCYLIB's actual uniform loop macro."""
import json,os,tempfile,unittest
from pathlib import Path
from test_project_header_logging import ROOT,run

@unittest.skipUnless(os.getenv('HEAPLENS_RUN_INSTRUMENTATION_TESTS')=='1','opt-in native C test')
class AscylibReadonly(unittest.TestCase):
    def test_zero_rng_cannot_mutate_zero_update_diagnostic(self):
        base=Path(os.environ.get('HEAPLENS_TEST_EVIDENCE',tempfile.gettempdir()))
        trial=Path(tempfile.mkdtemp(prefix='readonly-zero-',dir=base));(trial/'include').mkdir()
        header=trial/'include/main_test_loop.h'
        header.write_bytes((ROOT/'artifact/vendor/ascylib/include/main_test_loop.h').read_bytes())
        (trial/'probe.c').write_text(r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define WORKLOAD 0
#define unlikely(x) (x)
#define START_TS(...)
#define END_TS(...)
#define ADD_DUR(...)
#define END_TS_ELSE(...)
#define DS_ADD(...) 1
#define DS_REMOVE(...) 1
#define DS_CONTAINS(...) 1
typedef long sval_t;
static uint32_t chosen;
static uint32_t my_random(void* a,void* b,void* c) { return chosen; }
#include "include/main_test_loop.h"
int main(int argc,char** argv) {
  uint32_t c,key,rand_max=255,rand_min=0,seeds[3]={0};
  uint32_t scale_put=(uint32_t)strtoul(argv[2],0,10),scale_rem=(uint32_t)strtoul(argv[3],0,10);
  int my_putting_count=0,my_removing_count=0,my_getting_count=0;
  int my_putting_count_succ=0,my_removing_count_succ=0,my_getting_count_succ=0;
  chosen=(uint32_t)strtoul(argv[1],0,10);
  TEST_LOOP(NULL);
  printf("%d %d %d\n",my_putting_count,my_removing_count,my_getting_count);
}
''')
        run(['gcc','-std=c11','-O2','probe.c','-o','original'],trial)
        run(['python3',str(ROOT/'artifact/lib/ascylib_readonly.py'),str(trial)])
        run(['gcc','-std=c11','-O2','probe.c','-o','fixed'],trial)
        cases=[]
        selectors=(0,1,9,10,11,19,20,21,2147483648,4294967295)
        for put,remove in ((0,0),(0,20),(10,20),(4294967295,4294967295)):
            for value in selectors:
                args=list(map(str,(value,put,remove)))
                original=run([str(trial/'original'),*args],trial).strip()
                fixed=run([str(trial/'fixed'),*args],trial).strip()
                self.assertEqual(fixed,'0 0 1' if remove==0 else original)
                cases.append(dict(selector=value,put_threshold=put,update_threshold=remove,original=original,fixed=fixed))
        self.assertEqual(cases[0]['original'],'1 0 0')
        self.assertEqual(cases[0]['fixed'],'0 0 1')
        (trial/'verification.json').write_text(json.dumps(dict(status='passed',cases=cases),indent=2))
