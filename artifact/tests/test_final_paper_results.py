"""Check adopted cohorts, denominators and published rounding from saved cells."""
import importlib.util
import json
from pathlib import Path
import unittest

DATA=Path(__file__).resolve().parents[1]/'final-paper'
spec=importlib.util.spec_from_file_location('final_summary',DATA/'summarize.py')
summary=importlib.util.module_from_spec(spec);spec.loader.exec_module(summary)

class FinalPaperResults(unittest.TestCase):
    def test_adopted_table_and_buffer_ablation(self):
        cells=json.loads((DATA/'logging-cells.json').read_text())['cells']
        got=summary.logging_summary(cells)
        expected={
            'ascylib_efrb':(7010,6500,7.2,0), 'ascylib_dvy':(16700,16300,1.9,0),
            'tpcc_bcco':(969,550,43,17),'tpcc_efrb':(126,120,4.6,0),
            'rocks_hsl':(12600,5010,60,47),'rocks_isl':(5830,5870,-.67,0),
            'valkey':(1090,1030,5.6,0),'hnsw128':(66.3,64.6,2.5,0),'hnsw1536':(7.15,7.14,.20,0)}
        self.assertEqual(set(got),set(expected))
        for app,want in expected.items():
            x=got[app]
            values=(float(format(x['plain_mean']/1000,'.3g')),float(format(x['logging_mean']/1000,'.3g')),
                    float(format(x['loss_percent'],'.2g')),float(format(x['wait_percent'],'.2g')))
            self.assertEqual(values,want,app)
        b=got['tpcc_bcco']['buffer_ablation']
        self.assertEqual(round(b['adaptive_gain_percent'],1),18.1)
        self.assertEqual(round(b['adaptive_mean_peak_rss_gib']-b['fixed_mean_peak_rss_gib'],1),1.3)
        self.assertEqual(round(got['tpcc_bcco']['abort_attempt_percent']['logging'],1),10.5)
        self.assertEqual(round(got['rocks_hsl']['alternative_timing']['reader_only_loss_percent'],1),55.7)
        with self.assertRaises(ValueError):summary.logging_summary(cells+[cells[0]])
    def test_wait_uses_sum_of_worker_times_excludes_drain(self):
        row=dict(identity=dict(application='x'),waits=[
            dict(phase=1,begin_ns=10,end_ns=110,reuse_ns=20),
            dict(phase=1,begin_ns=10,end_ns=910,reuse_ns=0),
            dict(phase=2,begin_ns=10,end_ns=110,reuse_ns=100)])
        self.assertEqual(summary.wait_percent(row),2)
    def test_all_selection_scopes_and_published_rounding(self):
        data=json.loads((DATA/'selection-summary.json').read_text())
        got=summary.selection_summary(data['cells'])
        self.assertEqual([x['patterns_found_in_all_20'] for x in got['table4']],[12,12,11,10])
        self.assertEqual([round(x['duration_coverage_percent'],1) for x in got['table4']],[99,99.3,91.5,91.3])
        a={(x['rare_included'],x['page_budget']):x['arms'] for x in got['ablations']}
        self.assertEqual(round(a[False,128]['full']['duration_coverage_percent'],1),99.2)
        self.assertEqual(round(a[True,128]['no_per_time']['full_relative_gain_percent'],1),22.6)
        self.assertEqual(round(a[True,32]['no_alternation']['full_relative_gain_percent'],1),20.3)
        with self.assertRaises(ValueError):summary.selection_summary(data['cells'][:-1])
