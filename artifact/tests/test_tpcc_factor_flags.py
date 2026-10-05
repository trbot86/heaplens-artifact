"""Check tree selection required by the shared-reclaimer factor builds."""
from pathlib import Path
import shlex
import unittest
import os
import subprocess
import sys
import tempfile
import io
import json
from contextlib import redirect_stderr
from unittest.mock import patch

ART=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ART))
import ae


class SharedReclaimerFlags(unittest.TestCase):
    def test_cli_propagates_full_factors_and_records_it(self):
        for name in ('tpcc_bcco_bench','tpcc_efrb_bench'):
            for value in ('standard','full'):
                with tempfile.TemporaryDirectory() as tmp, patch.object(ae,'ART',Path(tmp)), patch.object(ae,'run') as run:
                    args=ae.parse_args(['experiment',name,'--tpcc-factors',value])
                    with patch.dict(os.environ,HEAPLENS_CR_FULL_FACTORS='unexpected'):
                        ae.experiment(args)
                    env=run.call_args.kwargs['env'];expected='1' if value=='full' else '0'
                    self.assertEqual(env['HEAPLENS_CR_FULL_FACTORS'],expected)
                    saved=json.loads((Path(env['ARTIFACT_RUN_DIR'])/'protocol.json').read_text())
                    self.assertEqual(saved['settings']['HEAPLENS_CR_FULL_FACTORS'],expected)
        for args in (['rocksdb'],['experiment','ascylib_efrb_bench'],['experiment','tpcc_efrb']):
            with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):ae.parse_args(args+['--tpcc-factors','full'])

    def test_actual_bash_factor_selection(self):
        for name,count in [('tpcc_bcco_bench',3),('tpcc_efrb_bench',5)]:
            source=(ART/'experiments'/name/'run.sh').read_text()
            body=source[source.index('echo "=== [$OUT_NAME] a_'):source.index('\nperfbench_run_campaign')]
            preamble='tpcc_perfbench_build() { :; }; tpcc_perfbench_variant() { printf "CELL:%s\\n" "$3"; };\n'
            for flag,expected in [('0',count),('1',count+2)]:
                result=subprocess.run(['bash','-c',preamble+body],env={**os.environ,'HEAPLENS_CR_FULL_FACTORS':flag},capture_output=True,text=True,check=True)
                cells=[line[5:] for line in result.stdout.splitlines() if line.startswith('CELL:')]
                self.assertEqual(len(cells),expected)
                if flag=='1':self.assertIn('d_lock_only' if name=='tpcc_bcco_bench' else 'f_padding_only_segregated',cells)

    def test_shared_reclaimer_selects_its_tree(self):
        artifact = Path(__file__).resolve().parents[1]
        for experiment, define in (("tpcc_bcco_bench", "-DBST_BRONSON"),
                                   ("tpcc_efrb_bench", "-DBST_ELLEN")):
            driver = artifact / "experiments" / experiment / "run.sh"
            builds = [shlex.split(line.strip()) for line in driver.read_text().splitlines()
                      if line.strip().startswith("tpcc_perfbench_build ")]
            shared = [build[-1].split() for build in builds
                      if "-DMACROBENCH_SINGLE_RECMGR" in build[-1].split()]
            self.assertTrue(shared, experiment)
            for flags in shared:
                with self.subTest(experiment=experiment, flags=flags):
                    self.assertIn(define, flags)
