"""Camera-ready selector regressions. No native logger/converter changes."""
from pathlib import Path
import random
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'sifter_vis_d3/server'))
from page_selection import select_pages


class FirstChoice:
    def shuffle(self, values): pass
    def choice(self, values): return values[0]
    def randrange(self, length): return 0


class SelectionTests(unittest.TestCase):
    def test_history_budget_reserves_cluster_coverage(self):
        clusters = {0: [1, 2, 3], 1: [4]}
        costs = {1: 2, 2: 30, 3: 40, 4: 25}
        pages, info = select_pages(clusters, {}, 128, page_records=costs,
                                  record_budget=27, rng=FirstChoice())
        self.assertEqual(pages, {1, 4})
        self.assertEqual(info['selected_records'], 27)
        self.assertEqual(info['omitted_clusters'], [])

    def test_history_budget_prefers_typical_not_cheapest(self):
        pages, _ = select_pages({0: [1, 2, 3]}, {}, 1,
                               page_records={1: 1, 2: 40, 3: 80},
                               record_budget=100, rng=FirstChoice())
        self.assertEqual(pages, {2})

    def test_128_dense_huge_pages_do_not_bypass_record_cap(self):
        costs = {p: 2097152//32 for p in range(128)}
        pages, info = select_pages({p: [p] for p in costs}, {}, 128,
                                  page_records=costs, record_budget=100000)
        self.assertEqual(len(pages), 1)
        self.assertEqual(info['selected_records'], 65536)
        self.assertEqual(len(info['omitted_clusters']), 127)

    def test_unaffordable_cluster_and_perf_exception(self):
        costs = {1: 1000, 2: 5}
        pages, info = select_pages({0: [1], 1: [2]}, {}, 128,
                                  page_records=costs, record_budget=10, rng=FirstChoice())
        self.assertEqual(pages, {2})
        self.assertEqual(info['omitted_clusters'], [0])
        self.assertEqual(info['oversized_pages'], 1)
        pages, info = select_pages({0: [1], 1: [2]}, {}, 128, forced_pages={1},
                                  page_records=costs, record_budget=10)
        self.assertEqual(pages, {1})
        self.assertEqual(info['perf_record_budget_excess'], 990)

    def test_history_extremes_follow_type_coverage(self):
        costs = {1: 2, 2: 20, 3: 100, 4: 10}
        pages, info = select_pages({0: [1, 2, 3, 4]}, {4: {'rare'}}, 2,
                                  page_records=costs, record_budget=200, rng=FirstChoice())
        self.assertIn(4, pages)
        self.assertEqual(info['omitted_types'], [])
        self.assertGreater(len(info['omitted_history_extremes']), 0)
        pages, info = select_pages({0: [1, 2, 3, 4]}, {4: {'rare'}}, 4,
                                  page_records=costs, record_budget=200, rng=FirstChoice())
        self.assertEqual(info['omitted_history_extremes'], [])

    def test_randomized_history_bounds_and_feasible_coverage(self):
        for seed in range(100):
            rng = random.Random(seed)
            clusters = {c: list(range(c*8, c*8+8)) for c in range(20)}
            costs = {p: rng.randrange(1, 10000) for pages in clusters.values() for p in pages}
            minimum = sum(min(costs[p] for p in pages) for pages in clusters.values())
            for cap in (0, minimum-1, minimum, 100000):
                pages, info = select_pages(clusters, {}, 128, page_records=costs,
                                          record_budget=cap, rng=random.Random(seed))
                self.assertLessEqual(sum(costs[p] for p in pages), cap)
                self.assertLessEqual(len(pages), 128)
                if cap >= minimum:
                    self.assertEqual(info['omitted_clusters'], [])

    def test_invalid_record_budget_and_counts(self):
        for cap in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                select_pages({}, {}, 1, page_records={}, record_budget=cap)
        with self.assertRaises(ValueError):
            select_pages({}, {}, 1, record_budget=10)
        with self.assertRaises(ValueError):
            select_pages({0: [1]}, {}, 1, page_records={1: -1}, record_budget=10)

    def test_cluster_pass_precedes_types_and_extra_runs(self):
        clusters={0:[1,2,3],1:[4,5],2:[6]}
        types={1:{'A'},2:{'B'},3:{'C'},4:{'A'},5:{'D'},6:{'A'}}
        pages, info=select_pages(clusters,types,3,rng=FirstChoice())
        self.assertEqual(pages,{1,4,6})
        self.assertEqual(info['omitted_clusters'],[])
        self.assertEqual(info['omitted_types'],['B','C','D'])
        pages,info=select_pages(clusters,types,5,rng=FirstChoice())
        self.assertEqual(pages,{1,2,3,4,6})
        self.assertEqual(info['pages_after_cluster_pass'],3)
        self.assertEqual(info['pages_after_type_pass'],5)

    def test_one_type_selection_can_cover_multiple_types(self):
        pages,info=select_pages({0:[1,2],1:[3]}, {1:{'A'},2:{'B','C'},3:{'A'}},
                               3,rng=FirstChoice())
        self.assertEqual(pages,{1,2,3})
        self.assertEqual(info['omitted_types'],[])

    def test_cluster_overflow_is_bounded_and_reported(self):
        pages,info=select_pages({i:[i] for i in range(10)}, {i:{'A'} for i in range(10)},
                               3,rng=FirstChoice())
        self.assertEqual(pages,{0,1,2})
        self.assertEqual(info['omitted_clusters'],list(range(3,10)))

    def test_duplicates_and_runs_do_not_overshoot(self):
        pages,info=select_pages({0:list(range(40)),1:[50,50,51]},
                               {p:{'A'} for p in range(52)},7,rng=FirstChoice())
        self.assertLessEqual(len(pages),7)
        self.assertIn(50,pages)
        self.assertEqual(info['perf_budget_excess'],0)

    def test_forced_pages_satisfy_cluster_and_type_coverage(self):
        pages,info=select_pages({0:[1,2],1:[3]}, {1:{'A'},2:{'B'},3:{'C'}},
                               2,forced_pages={2,999},rng=FirstChoice())
        self.assertEqual(pages,{2,3})
        self.assertEqual(info['mandatory_perf_pages'],1)
        self.assertEqual(info['omitted_types'],['A'])

    def test_mandatory_perf_overflow_is_only_budget_exception(self):
        pages,info=select_pages({0:[1,2],1:[3,4]}, {p:{str(p)} for p in range(1,5)},
                               1,forced_pages={1,2,3},rng=FirstChoice())
        self.assertEqual(pages,{1,2,3})
        self.assertEqual(info['perf_budget_excess'],2)

    def test_empty_zero_budget_and_missing_types(self):
        self.assertEqual(select_pages({}, {}, 0)[0],set())
        pages,info=select_pages({0:[1]}, {1:{'A'}}, 0)
        self.assertEqual(pages,set())
        self.assertEqual(info['omitted_types'],['A'])
        pages,info=select_pages({0:[1,2]}, {1:{'A'},2:{'B'}},1,
                               coverage_types={'A','absent'},rng=FirstChoice())
        self.assertEqual(info['omitted_types'],[])
        self.assertEqual(info['eligible_types'],['A'])

    def test_randomized_invariants(self):
        clusters={i:list(range(i*23,(i+1)*23)) for i in range(20)}
        types={p:{f't{p%31}',f't{p%7}'} for p in range(460)}
        for seed in range(50):
            for budget in (0,1,17,20,52,128):
                with self.subTest(seed=seed,budget=budget):
                    pages,info=select_pages(clusters,types,budget,rng=random.Random(seed))
                    self.assertLessEqual(len(pages),budget)
                    self.assertEqual(len(pages),info['selected_pages'])
                    self.assertEqual(info['represented_clusters'],min(budget,20))
                    if budget>=51:
                        self.assertEqual(info['omitted_types'],[])
                    self.assertEqual((pages,info),select_pages(clusters,types,budget,rng=random.Random(seed)))

    def test_invalid_budgets(self):
        for budget in (-1,1.5,True):
            with self.assertRaises(ValueError): select_pages({}, {}, budget)


class SamplerIntegrationTests(unittest.TestCase):
    def sample(self, budget, forced=(), record_budget=None):
        import pandas as pd
        from sampler import Sampler
        from unittest.mock import Mock
        sampler=Sampler.__new__(Sampler)
        sampler.page_size=4096
        pages=[10,11,12,20]
        data=pd.DataFrame({0:[[['test.cpp',16,p*4096,'A' if p!=11 else 'B',1,float('nan'),5,p*4096]]
                              for p in pages], 'cluster':[0,0,0,1]},
                          index=pd.Index(pages,name='page_num'))
        features=pd.DataFrame({'A 0':[3,0,3,3],'B 0':[0,3,0,0],'cluster':[0,0,0,1]},
                              index=data.index)
        sampler.get_clusters_of_pages=Mock(return_value=(data,features,pd.DataFrame({'page_num':list(forced)})))
        random.seed(47)
        return sampler.get_sample_of_pages(-1,-1,{'A':True,'B':True},'mbkmeans',5,3,
                                          page_budget=budget,record_budget=record_budget)

    def test_record_count_matches_serialized_histories(self):
        result = self.sample(128, record_budget=2)
        self.assertEqual(sum(len(p['events']) for p in result['page_num_events'].values()), 2)
        self.assertEqual(result['selection']['selected_records'], 2)

    def test_payload_and_json_compatibility(self):
        from flask import Flask
        result=self.sample(3)
        self.assertEqual(len(result['page_num_events']),3)
        self.assertEqual(len(result['clusters']),2)
        self.assertEqual(result['selection']['omitted_types'],[])
        self.assertEqual(result['num_clusters'],2)
        self.assertEqual(result['sum_cluster_sizes'],4)
        self.assertEqual({e['type'] for p in result['page_num_events'].values() for e in p['events']},{'A','B'})
        encoded=Flask(__name__).json.dumps(result)
        self.assertIn('cluster-first-type-coverage',encoded)

    def test_zero_budget_keeps_payload_shape(self):
        result=self.sample(0)
        self.assertEqual(result['page_num_events'],{})
        self.assertEqual(result['clusters'],{})
        self.assertEqual(result['num_clusters'],2)
        self.assertEqual(result['selection']['omitted_clusters'],[0,1])

    def test_perf_exception_is_explicit_in_payload(self):
        result=self.sample(1,forced=(10,20))
        self.assertEqual(len(result['page_num_events']),2)
        self.assertEqual(result['selection']['perf_budget_excess'],1)


if __name__=='__main__': unittest.main()
