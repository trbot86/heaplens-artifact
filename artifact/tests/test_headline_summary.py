import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1] / 'headline-pmu'
spec = importlib.util.spec_from_file_location('headline_summary', PACKAGE/'summarize.py')
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


class RetainedSummary(unittest.TestCase):
    def test_all_cells_and_comparisons(self):
        self.assertEqual(len(summary.summarize(PACKAGE/'campaign-numerical-summary.json')), 20)

    def test_duplicate_cell_rejected(self):
        data = json.loads((PACKAGE/'campaign-numerical-summary.json').read_text())
        data['rows'][-1] = data['rows'][0]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'invalid.json'; path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                summary.summarize(path)
