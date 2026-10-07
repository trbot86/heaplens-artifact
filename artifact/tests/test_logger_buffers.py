"""Optional bounded-buffer prototype: real AIO faults and deterministic pressure."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]

class LoggerBuffers(unittest.TestCase):
    def test_pressure_memory_cap_thread_churn_and_aio_faults(self):
        base=Path(os.environ.get('HEAPLENS_TEST_EVIDENCE',tempfile.gettempdir()))
        trial=Path(tempfile.mkdtemp(prefix='buffer-pressure-',dir=base))
        reports=[]
        for slots,budget,fail_growth,scan in [(2,0,False,0),(2,0,False,1),(4,0,False,1),(4,160,False,1),(4,320,False,1),(8,480,False,1),(4,320,True,1)]:
            folder=trial/f'{slots}-{budget}-{fail_growth}-{scan}';folder.mkdir()
            flags=['g++','-std=c++11','-O2','-pthread','-I'+str(ROOT/'memhook'),
                   '-DMEMHOOK_MAX_BUFFER_SIZE=4',f'-DMEMHOOK_MAX_BUFFERS={slots}',
                   f'-DMEMHOOK_EXTRA_BUFFER_BUDGET_BYTES={budget}',f'-DMEMHOOK_REUSE_COMPLETED_BUFFERS={scan}']
            binary=folder/'pressure'
            p=subprocess.run(flags+[str(ROOT/'artifact/tests/fixtures/logger_buffer_pressure.cpp'),'-o',str(binary),'-Wl,--wrap=malloc','-lrt'],
                             capture_output=True,text=True,timeout=60)
            (folder/'build.log').write_text(p.stdout+p.stderr)
            self.assertEqual(p.returncode,0,p.stderr)
            for count in (0,1,4,5,40,43):
                p=subprocess.run([str(binary),str(count),str(folder/f'pressure-{count}.bin')],
                                 capture_output=True,text=True,timeout=20,
                                 env={**os.environ,**({'MEMHOOK_TEST_FAIL_GROW':'1'} if fail_growth else {})})
                (folder/f'pressure-{count}.log').write_text(p.stdout+p.stderr)
                self.assertEqual(p.returncode,0,p.stderr)
                reports.append(dict(slots=slots,budget=budget,count=count,fail_growth=fail_growth,scan=scan,**json.loads(p.stdout.strip().splitlines()[-1])))
            if fail_growth:continue
            binary=folder/'faults'
            p=subprocess.run(flags+[str(ROOT/'artifact/tests/fixtures/logger_lifecycle.cpp'),'-o',str(binary),
                '-Wl,--wrap=aio_write,--wrap=aio_error,--wrap=aio_suspend,--wrap=aio_return','-lrt'],
                capture_output=True,text=True,timeout=60)
            (folder/'fault-build.log').write_text(p.stdout+p.stderr)
            self.assertEqual(p.returncode,0,p.stderr)
            for fault in range(6):
                p=subprocess.run([str(binary),'43',str(fault),str(folder/f'fault-{fault}.bin')],
                                 capture_output=True,text=True,timeout=20)
                (folder/f'fault-{fault}.log').write_text(p.stdout+p.stderr)
                self.assertEqual(p.returncode,0 if fault in (0,1) else 94,p.stderr)
                if fault>=2:self.assertIn('trace invalid',p.stderr)
        (trial/'verification.json').write_text(json.dumps(dict(status='passed',cases=reports,real_aio_fault_cases=36),indent=2)+'\n')
