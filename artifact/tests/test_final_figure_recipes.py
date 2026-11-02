"""Final figure defaults, CLI forwarding and phase boundaries."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'artifact'))
import ae
from lib.bcco_figure import apply
from lib.hj_figure import apply as apply_hj


class FigureRecipes(unittest.TestCase):
    def command(self, argv, folder):
        with patch.object(sys,'argv',['ae.py',*argv]): args=ae.parse_args()
        with patch.object(ae,'new_output',return_value=folder),patch.object(ae,'ART',folder),patch.object(ae,'run') as run,\
             patch.object(ae,'node_cpus',return_value=list(range(args.threads or 24))):
            ae.experiment(args)
            return run.call_args.kwargs['env']
    def test_efrb_final_four_workers_and_explicit_overrides(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            for profile,want in [('paper','4'),('smoke','2')]:
                env=self.command(['experiment','ascylib_efrb','--profile',profile],out)
                self.assertEqual(env['THREADS'],want)
            env=self.command(['experiment','ascylib_efrb','--profile','paper','--threads','2'],out)
            self.assertEqual(env['THREADS'],'2')
    def test_bcco_recipe_records_isolated_factor_and_placement(self):
        with tempfile.TemporaryDirectory() as td:
            for variant in ('baseline','segregation-only'):
                env=self.command(['experiment','tpcc_bcco','--profile','paper','--variant',variant,
                    '--bcco-figure','--cpus','0-23','--memory-policy','bind'],Path(td))
                self.assertEqual(env['THREADS'],'24')
                self.assertEqual(env['TRACE_VARIANT'],variant)
                self.assertEqual(env['SAMPLE_PROPORTION'],'0.02')
                self.assertEqual(env['TRACE_MEMORY'],'membind')
                receipt=json.loads((Path(td)/'protocol.json').read_text())
                self.assertEqual(receipt['settings']['HEAPLENS_BCCO_FIGURE'],'1')
    def test_hj_walkthrough_configuration_and_allocator(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            env=self.command(['experiment','tpcc_hj','--profile','paper'],root)
            self.assertEqual(env['THREADS'],'24')
            self.assertEqual(env['SAMPLE_PROPORTION'],'0.01')
            self.assertEqual(env['SAMPLE_SEED'],'20261009')
            vendor=ROOT/'artifact/vendor/setbench'
            for rel in ('ds/howley_int_bst_lf/howley_impl.h','lib/libjemalloc.so'):
                dest=root/rel;dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(vendor/rel,dest)
            apply_hj(root)
            self.assertNotIn('#define LARGE_DES\n',(root/'ds/howley_int_bst_lf/howley_impl.h').read_text())
            with self.assertRaises(ValueError):apply_hj(root)
    def test_backing_probes_are_outside_native_interval(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'system').mkdir()
            shutil.copy2(ROOT/'artifact/vendor/setbench/macrobench/system/main.cpp',root/'system/main.cpp')
            apply(root,'segregation-only')
            s=(root/'system/main.cpp').read_text()
            self.assertIn('hl_fig9_identity(true)',s)
            self.assertLess(s.index('hl_fig9_snapshot("measurement_start")'),s.index('int64_t starttime'))
            self.assertGreater(s.index('hl_fig9_snapshot("measurement_end")'),s.index('int64_t endtime'))
            with self.assertRaises(ValueError):apply(root,'segregation-only')
    def test_bcco_figure_rejects_combined_factor(self):
        with patch.object(sys,'argv',['ae.py','experiment','tpcc_bcco','--variant','optimized','--bcco-figure']):
            with self.assertRaises(SystemExit):ae.parse_args()
