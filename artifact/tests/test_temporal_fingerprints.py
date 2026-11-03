"""Opt-in temporal prototype: no target-workload knowledge in selection."""
from pathlib import Path
import random
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'sifter_vis_d3/server'))
from temporal_fingerprints import (regular_times, histogram, quantize,
                                   snapshot_counts, compress_observations, cluster_pages,
                                   cluster_features)
from page_selection import select_pages


class FirstChoice:
    def shuffle(self, values): pass
    def choice(self, values): return values[0]
    def randrange(self, length): return 0


class TemporalTests(unittest.TestCase):
    def test_integer_schedule_at_large_timestamps(self):
        start = 2**60+3
        self.assertEqual(regular_times(start, start+17, 4),
                         [start, start+5, start+11, start+17])
        self.assertEqual(regular_times(7, 7), [7])
        with self.assertRaises(ValueError): regular_times(2, 1)

    def test_live_snapshots_keep_types_and_exact_byte_alignments(self):
        rows = pd.DataFrame(dict(addr=[4096, 4096, 4163, 8192],
                                 type=['old', 'new', 'odd', 'other'],
                                 allocTs=[1, 5, 1, 9], freeTs=[5, None, 8, None]))
        counts, meta = snapshot_counts(rows, [1, 5, 8])
        self.assertEqual([x['page'] for x in meta], [1, 1, 1])
        self.assertEqual(counts['old 0'].tolist(), [1, 0, 0])
        self.assertEqual(counts['new 0'].tolist(), [0, 1, 1])
        self.assertEqual(counts['odd 67'].tolist(), [1, 1, 0])
        # All-time histogram counts both successive occupants at one address.
        self.assertEqual(int(histogram(rows).loc[1].sum()), 3)

    def test_duplicate_vectors_preserve_every_time_and_source(self):
        counts = pd.DataFrame({'A 0':[1, 1, 1, 1], 'B 0':[0, 0, 0, 1]})
        meta = [dict(page=p, timestamp=t, source=s) for p,t,s in
                [(1, 3, 'regular'), (1, 7, 'max_fill'), (2, 3, 'regular'), (1, 9, 'regular')]]
        obs = compress_observations(counts, meta)
        self.assertEqual(obs.raw_observations, 4)
        self.assertEqual(len(obs.features), 3)
        self.assertEqual(obs.metadata[0]['times'], [(3, 'regular'), (7, 'max_fill')])
        self.assertEqual([m['page'] for m in obs.metadata], [1, 2, 1])
        with self.assertRaises(ValueError): compress_observations(counts, meta[:1])

    def test_empty_and_count_quantization(self):
        self.assertTrue(compress_observations(pd.DataFrame(), []).features.empty)
        values = quantize(pd.DataFrame({'A':[0, 1, 100], 'B':[0, 0, 0]}))
        self.assertEqual(values.A.tolist(), [0, 1, 3])
        self.assertEqual(values.B.tolist(), [0, 0, 0])

    def test_max_fill_time_materialization_includes_containers(self):
        rows = pd.DataFrame(dict(addr=[4096, 4160], type=['slab', 'node'],
                                 allocTs=[1, 2], freeTs=[None, None]))
        snapshots = pd.DataFrame(dict(page_num=[1], snapshot_ts=[2]))
        counts, meta = snapshot_counts(rows, max_fill=snapshots)
        self.assertEqual(int(counts.iloc[0].sum()), 2)
        self.assertEqual(meta, [dict(page=1, timestamp=2, source='max_fill')])

    def test_cluster_membership_deduplicates_pages(self):
        self.assertEqual(cluster_pages([2, 2, 1], [7, 7, 8], 10), {12:[7], 11:[8]})

    def test_clustering_replays_across_input_array_layouts(self):
        values = np.random.RandomState(7).randint(0, 4, size=(500, 8))
        labels = [cluster_features(pd.DataFrame(np.array(values, order=order)), 4, 17)
                  for order in ('C', 'F')]
        np.testing.assert_array_equal(*labels)

    def test_one_page_can_cover_two_clusters_without_double_charge(self):
        pages, info = select_pages({0:[1, 2], 1:[2, 3]}, {}, 1,
                                  page_records={1:8, 2:8, 3:8}, record_budget=8,
                                  rng=FirstChoice(), overlapping_clusters=True)
        self.assertEqual(pages, {2})
        self.assertEqual(info['selected_records'], 8)
        self.assertEqual(info['omitted_clusters'], [])

    def test_overlapping_forced_page_and_budget_exception(self):
        pages, info = select_pages({0:[1, 2], 1:[2, 3]}, {}, 0, forced_pages=[2],
                                  page_records={1:8, 2:8, 3:8}, record_budget=0,
                                  overlapping_clusters=True)
        self.assertEqual(pages, {2})
        self.assertEqual(info['omitted_clusters'], [])
        self.assertEqual(info['perf_record_budget_excess'], 8)

    def test_randomized_overlapping_bounds_and_replay(self):
        for seed in range(40):
            rng = random.Random(seed)
            clusters = {c:rng.sample(range(40), 15) for c in range(12)}
            costs = {p:rng.randrange(1, 30) for p in range(40)}
            args = dict(page_records=costs, record_budget=150, overlapping_clusters=True)
            selected, info = select_pages(clusters, {}, 10, rng=random.Random(seed), **args)
            self.assertLessEqual(len(selected), 10)
            self.assertEqual(info['selected_records'], sum(costs[p] for p in selected))
            self.assertLessEqual(info['selected_records'], 150)
            self.assertEqual(info['omitted_clusters'], sorted(c for c,ps in clusters.items()
                                                            if not set(ps)&selected))
            self.assertEqual((selected, info), select_pages(clusters, {}, 10,
                                                         rng=random.Random(seed), **args))


if __name__ == '__main__': unittest.main()
