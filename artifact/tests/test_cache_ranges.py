"""Equal-output checks against the previous repeated-index accumulation."""
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import Mock, patch
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'sifter_vis_d3/server'))
from cache_ranges import add_cache_range
from sampler import Sampler, event_labels


def reference(data, bucket, start_set, type_idx, count, num_sets, delta):
    np.add.at(data, (np.full(count, bucket), (start_set + np.arange(count)) % num_sets,
                    np.full(count, type_idx)), delta)


class CacheRangesTest(unittest.TestCase):
    def test_boundaries_and_repeated_sets(self):
        for sets in (1, 2, 7, 64):
            for start in range(sets):
                for count in (0, 1, sets - 1, sets, sets + 1, 3 * sets + 5):
                    for delta in (-1, 1):
                        old = np.zeros((3, sets, 4)); new = old.copy()
                        reference(old, 1, start, 2, count, sets, delta)
                        add_cache_range(new, 1, start, 2, count, sets, delta)
                        np.testing.assert_array_equal(new, old)

    def test_mixed_updates(self):
        rng = random.Random(47)
        for sets in (1, 8, 64, 512):
            old = np.zeros((17, sets, 9)); new = old.copy()
            for _ in range(1000):
                args = (rng.randrange(17), rng.randrange(sets), rng.randrange(9),
                        rng.randrange(5 * sets), sets, rng.choice((-1, 1)))
                reference(old, *args); add_cache_range(new, *args)
            np.testing.assert_array_equal(new, old)

    def test_negative_count_is_rejected(self):
        with self.assertRaises(ValueError):
            add_cache_range(np.zeros((1, 1, 1)), 0, 0, 0, -1, 1, 1)

    def test_integrated_sampler_with_fields_and_frees(self):
        s = Sampler.__new__(Sampler)
        s.page_size, s.cache_line_size, s.num_buckets = 4096, 64, 20
        s.min_ts, s.max_ts, s.all_data = 0, 100, None
        rows = [['test', 5000, 63, 'Node', 1, 70, 1, 63],
                ['test', 64, 4096, 'Node', 70, float('nan'), 1, 4096],
                ['test', 0, 8192, 'Empty', 10, 10, 2, 8192],
                ['test', 3, 4100, 'Node', 5, 90, 1, 4090]]
        s.get_objects = Mock(return_value=pd.DataFrame([r + [0] for r in rows], columns=event_labels))
        s.types = Mock(return_value=['Node', 'Empty'])
        s.get_fields = Mock(return_value={'Node': [dict(subtype='field', offset=4, size=64)]})
        actual = s.get_cache_data(32768, 8)
        with patch('sampler.add_cache_range', reference):
            expected = s.get_cache_data(32768, 8)
        self.assertEqual(actual, expected)


if __name__ == '__main__': unittest.main()
