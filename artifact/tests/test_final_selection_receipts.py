import copy
import gzip
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1] / 'final-paper'
spec = importlib.util.spec_from_file_location('verify_selection_receipts', HERE/'verify_selection.py')
verification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verification)


class SavedSelectionReceipts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(HERE/'selection-trials.json.gz', 'rt', encoding='utf-8') as stream:
            cls.trials = json.load(stream)
        cls.summary = json.loads((HERE/'selection-summary.json').read_text(encoding='utf-8'))

    def test_all_final_aggregates_reproduce(self):
        self.assertEqual(verification.verify(self.trials, self.summary), dict(
            trials=440, method_budget_outputs=3520, aggregate_cells=208, all_aggregates_match=True))

    def test_missing_or_duplicate_seed_rejected(self):
        for rows in (self.trials['trials'][:-1], self.trials['trials'] + [self.trials['trials'][0]]):
            with self.assertRaisesRegex(ValueError, 'trial identity'):
                verification.verify({**self.trials, 'trials': rows}, self.summary)

    def test_changed_paper_aggregate_rejected(self):
        altered = copy.deepcopy(self.summary)
        altered['cells'][0]['duration_coverage_mean'] += .01
        with self.assertRaisesRegex(ValueError, 'Coverage mismatch'):
            verification.verify(self.trials, altered)


if __name__ == '__main__':
    unittest.main()
