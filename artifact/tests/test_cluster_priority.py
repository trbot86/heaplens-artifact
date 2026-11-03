"""Priority policy checks independent of workload anomaly predicates."""
from pathlib import Path
import random
import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'sifter_vis_d3/server'))
from cluster_priority import ClusterGeometry
from page_selection import select_pages
from temporal_fingerprints import cluster_features


class FirstChoice:
    def shuffle(self, values): pass
    def choice(self, values): return values[0]
    def randrange(self, length): return 0


class PriorityTests(unittest.TestCase):
    def test_common_seed_then_distinct_layout(self):
        clusters = {0:[1, 2, 3], 1:[4], 2:[5]}
        geometry = ClusterGeometry({0:[0], 1:[10], 2:[1]})
        pages, _ = select_pages(clusters, {}, 2, rng=FirstChoice(),
                               cluster_priority='novelty', cluster_geometry=geometry)
        self.assertEqual(pages, {1, 4})

    def test_exact_novelty_tie_favors_rarity(self):
        groups = {0:[0, 1, 2], 1:[3, 4], 2:[5]}
        state = ClusterGeometry({0:[0], 1:[-10], 2:[10]}).state(groups)
        self.assertEqual(state.choose([0, 1, 2], set()), 0)
        self.assertEqual(state.choose([1, 2], {0}), 2)

    def test_a_new_family_gets_common_seed(self):
        groups = {0:[0, 1], 1:[2], 2:[3, 4, 5], 3:[6]}
        state = ClusterGeometry({0:[0], 1:[100], 2:[0, 0], 3:[1, 1]},
                                {0:'history', 1:'history', 2:'time', 3:'time'}).state(groups)
        self.assertEqual(state.choose(list(groups), set()), 2)
        self.assertEqual(state.choose([0, 1, 3], {2}), 0)

    def test_family_rescaling_does_not_change_priority(self):
        groups = {i:[i] for i in range(6)}
        centers = {0:[0], 1:[2], 2:[7], 3:[0, 0], 4:[2, 1], 5:[4, 7]}
        families = {i:i//3 for i in groups}
        geometries = [ClusterGeometry(centers, families),
                      ClusterGeometry({c:np.array(v)*(1000 if c>=3 else 1)
                                       for c,v in centers.items()}, families)]
        states = [g.state(groups) for g in geometries]
        covered = {0, 3}
        pending = [1, 2, 4, 5]
        while pending:
            a, b = [s.choose(pending, covered) for s in states]
            self.assertEqual(a, b)
            covered.add(a); pending.remove(a)

    def test_selected_page_credits_every_membership(self):
        groups = {0:[1, 2, 3], 1:[1], 2:[4]}
        geometry = ClusterGeometry({0:[0], 1:[100], 2:[2]})
        pages, info = select_pages(groups, {}, 2, rng=FirstChoice(), overlapping_clusters=True,
                                  cluster_priority='novelty', cluster_geometry=geometry)
        self.assertEqual(pages, {1, 4})
        self.assertEqual(info['omitted_clusters'], [])

    def test_mandatory_pages_seed_distance_and_may_exceed_caps(self):
        groups = {0:[0, 1], 1:[2], 2:[3]}
        geometry = ClusterGeometry({0:[0], 1:[100], 2:[1]})
        for budget, records in ((2, 2), (0, 0)):
            pages, info = select_pages(groups, {}, budget, rng=FirstChoice(), forced_pages=[1],
                page_records={p:1 for p in range(4)}, record_budget=records,
                cluster_priority='novelty', cluster_geometry=geometry)
            self.assertEqual(pages, {1, 2} if budget else {1})
            self.assertEqual(info['perf_budget_excess'], 0 if budget else 1)

    def test_unaffordable_cluster_does_not_block_other_clusters(self):
        groups = {0:[0, 1, 2], 1:[3], 2:[4]}
        pages, _ = select_pages(groups, {}, 2, rng=FirstChoice(),
            page_records={0:1, 1:1, 2:1, 3:100, 4:1}, record_budget=2,
            cluster_priority='novelty', cluster_geometry=ClusterGeometry({0:[0], 1:[10], 2:[1]}))
        self.assertEqual(pages, {0, 4})

    def test_incremental_scores_match_direct_distance_oracle(self):
        for seed in range(30):
            rng = np.random.RandomState(seed)
            centers = {c:rng.randn(5 if c<8 else 3) for c in range(16)}
            families = {c:c//8 for c in centers}
            groups = {c:list(range(c+1)) for c in centers}
            geometry = ClusterGeometry(centers, families)
            state = geometry.state(groups)
            pending = list(centers); random.Random(seed).shuffle(pending)
            covered = set()
            while pending:
                unseeded = [c for c in pending if not any(families[x]==families[c] for x in covered)]
                if unseeded:
                    expected = max(unseeded, key=lambda c:len(groups[c]))
                else:
                    def score(c):
                        peers = [x for x in centers if families[x]==families[c]]
                        scale = sum(sum((centers[x]-centers[y])**2) for x in peers for y in peers if x!=y)/(len(peers)*(len(peers)-1))
                        distance = min(sum((centers[c]-centers[x])**2) for x in covered if families[x]==families[c])
                        return distance/scale, -len(groups[c])
                    expected = max(pending, key=score)
                actual = state.choose(pending, covered)
                self.assertEqual(actual, expected)
                covered.add(actual); pending.remove(actual)

    def test_randomized_budgets_replay_and_default_compatibility(self):
        for seed in range(40):
            rng = random.Random(seed)
            groups = {c:rng.sample(range(30), 7) for c in range(12)}
            costs = {p:rng.randrange(1, 15) for p in range(30)}
            geometry = ClusterGeometry({c:[rng.random(), rng.random()] for c in groups})
            for priority in ('shuffled', 'rarest', 'novelty', 'balanced50', 'balanced25'):
                args = dict(page_records=costs, record_budget=45, overlapping_clusters=True,
                            cluster_priority=priority, cluster_geometry=geometry)
                result = select_pages(groups, {}, 8, rng=random.Random(seed), **args)
                self.assertEqual(result, select_pages(groups, {}, 8, rng=random.Random(seed), **args))
                pages, info = result
                self.assertLessEqual(len(pages), 8)
                self.assertLessEqual(sum(costs[p] for p in pages), 45)
                self.assertEqual(info['omitted_clusters'], sorted(c for c,ps in groups.items() if not set(ps)&pages))
                if priority.startswith('balanced'):
                    n = info['pages_after_cluster_pass']
                    period = 2 if priority=='balanced50' else 4
                    self.assertEqual(info['cluster_priority_additions'],
                                     {'shuffled':n-n//period, 'novelty':n//period})
                if priority=='shuffled':
                    del args['cluster_priority']; del args['cluster_geometry']
                    self.assertEqual(result, select_pages(groups, {}, 8, rng=random.Random(seed), **args))

    def test_balanced_half_and_quarter_sequences(self):
        groups = {c:[c] for c in range(6)}
        geometry = ClusterGeometry({c:[c if c<5 else 100] for c in groups})
        for policy, expected, counts in (
                ('balanced50', {0,1,4,5}, {'shuffled':2,'novelty':2}),
                ('balanced25', {0,1,2,5}, {'shuffled':3,'novelty':1})):
            pages, info = select_pages(groups, {}, 4, rng=FirstChoice(),
                                      cluster_priority=policy, cluster_geometry=geometry)
            self.assertEqual(pages, expected)
            self.assertEqual(info['cluster_priority_additions'], counts)

    def test_balanced_failed_choice_keeps_same_turn(self):
        groups = {c:[c] for c in range(6)}
        geometry = ClusterGeometry({c:[c if c<5 else 100] for c in groups})
        pages, info = select_pages(groups, {}, 3, rng=FirstChoice(),
            page_records={c:100 if c==5 else 1 for c in groups}, record_budget=3,
            cluster_priority='balanced50', cluster_geometry=geometry)
        self.assertEqual(pages, {0,1,4})
        self.assertEqual(info['cluster_priority_additions'], {'shuffled':2,'novelty':1})

    def test_balanced_overlap_and_forced_pages_do_not_consume_turns(self):
        groups = {0:[0], 1:[0], 2:[1], 3:[2], 4:[3]}
        geometry = ClusterGeometry({c:[c] for c in groups})
        pages, info = select_pages(groups, {}, 3, rng=FirstChoice(), forced_pages=[0],
            overlapping_clusters=True, cluster_priority='balanced50', cluster_geometry=geometry)
        self.assertEqual(pages, {0,1,3})
        self.assertEqual(info['cluster_priority_additions'], {'shuffled':1,'novelty':1})
        for policy in ('balanced50','balanced25'):
            pages, info = select_pages(groups, {}, 0, forced_pages=[0],
                cluster_priority=policy, cluster_geometry=geometry)
            self.assertEqual(pages, {0})
            self.assertEqual(info['cluster_priority_additions'], {'shuffled':0,'novelty':0})
            with self.assertRaises(ValueError): select_pages(groups, {}, 1, cluster_priority=policy)

    def test_returning_centers_preserves_labels_and_rng(self):
        frame = pd.DataFrame(np.random.RandomState(8).randint(0, 4, size=(200, 10)))
        np.random.seed(13); old = cluster_features(frame, 4); next_old = np.random.rand()
        np.random.seed(13); labels, centers = cluster_features(frame, 4, return_centers=True)
        np.testing.assert_array_equal(old, labels)
        self.assertEqual(next_old, np.random.rand())
        self.assertEqual(set(centers), set(labels))
        self.assertEqual(cluster_features(frame.iloc[:0], 4, return_centers=True)[1], {})
        np.testing.assert_array_equal(cluster_features(frame.iloc[:1], 4, return_centers=True)[1][0], np.zeros(10))

    def test_empty_identical_and_invalid_geometry(self):
        self.assertEqual(select_pages({}, {}, 0, cluster_priority='novelty',
                                      cluster_geometry=ClusterGeometry({}))[0], set())
        state = ClusterGeometry({0:[1], 1:[1]}).state({0:[0, 1], 1:[2]})
        self.assertEqual(state.choose([1], {0}), 1)
        self.assertEqual(state.nearest[1], 0)
        with self.assertRaises(ValueError): ClusterGeometry({0:[float('nan')]})
        with self.assertRaises(ValueError): ClusterGeometry({0:[1]}, {1:'wrong'})
        with self.assertRaises(ValueError): select_pages({}, {}, 1, cluster_priority='bad')
        with self.assertRaises(ValueError): select_pages({}, {}, 1, cluster_priority='novelty')
        with self.assertRaises(ValueError): ClusterGeometry({0:[0]}).state({1:[0]})


if __name__ == '__main__': unittest.main()
