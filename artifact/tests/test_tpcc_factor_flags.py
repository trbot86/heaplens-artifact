"""Check tree selection required by the shared-reclaimer factor builds."""
from pathlib import Path
import shlex
import unittest


class SharedReclaimerFlags(unittest.TestCase):
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
