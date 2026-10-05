import importlib.util
import json
from pathlib import Path
import unittest

PACKAGE = Path(__file__).resolve().parents[1] / 'headline-pmu'
spec = importlib.util.spec_from_file_location('validation_summary', PACKAGE/'verify_validation.py')
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


class ValidationSummary(unittest.TestCase):
    def test_all_cells_and_original_hashes(self):
        self.assertEqual(summary.verify()['status'], 'passed')

    def test_missing_identity_and_changed_ratio_rejected(self):
        for change in ('identity', 'ratio'):
            data = json.loads((PACKAGE/'aio-validation/numerical-summary.json').read_text())
            if change == 'identity': data['cells'][-1] = data['cells'][0]
            else: data['summary']['bcco']['ratio_of_means']['fixed_vs_old_percent'] += 1
            with self.assertRaises(ValueError): summary.verify_aio(data)

    def test_changed_endpoint_rejected(self):
        data = json.loads((PACKAGE/'hsl-timing/numerical-summary.json').read_text())
        inputs = json.loads((PACKAGE/'hsl-timing/endpoint-reports.json').read_text())
        inputs[0]['text'] = inputs[0]['text'].replace('"logical_id":0', '"logical_id":1')
        with self.assertRaises(ValueError): summary.verify_hsl(data, inputs)
