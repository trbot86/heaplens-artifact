"""Compare the ordinary backend with preserved executed-study code."""
from pathlib import Path
import json
import random
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import numpy as np
import pandas as pd
from scipy import sparse

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'sifter_vis_d3/server'), str(Path(__file__).parent/'fixtures')]
from sampler import Sampler
from representative_selection import fingerprint_inputs, prepare_selection, derived_seed, MODES
from temporal_fingerprints import regular_times, quantize, compress_observations, cluster_features, cluster_pages
from cluster_priority import ClusterGeometry
from page_selection import select_pages
import study_page_selection
from study_features import numeric_features, MatrixBuilder


def objects():
    rng = random.Random(251)
    rows = []
    for page in range(1, 25):
        for i in range(1 + page % 8):
            ts = rng.randrange(100)
            rows.append(dict(addr=page*4096+i*17, type=f'T{page%3}', allocTs=ts,
                             freeTs=None if i%2 else ts+1+rng.randrange(30),
                             file='fixture.cpp', size=16, line=1,
                             actualAddr=page*4096+i*17, actualSize=16))
    df = pd.DataFrame(rows)
    df['freeTs'] = df.freeTs.astype('Int64')
    return df


def frozen_features(frame, start=0, end=130):
    times = regular_times(start, end)
    history, temporal = MatrixBuilder(), MatrixBuilder()
    for page, rows in frame.groupby(frame.addr//4096):
        hist, snaps = numeric_features(rows, times)
        history.append(page, 0, hist)
        for snap in snaps:
            temporal.append(page, snap['first'], snap['counts'])
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        history.finish(root, 'history'); temporal.finish(root, 'temporal')
        def load(name):
            index = np.load(root/(name+'-index.npz'))
            data = sparse.load_npz(root/(name+'.npz')).toarray()
            df = pd.DataFrame(data, columns=json.loads((root/(name+'-columns.json')).read_text()))
            return df, index
        hist, hi = load('history'); raw, ti = load('temporal')
        hist.index = hi['pages']; hist.index.name = 'page_num'
        meta = [dict(page=int(p), timestamp=times[int(t)], source='regular')
                for p,t in zip(ti['pages'],ti['first'])]
        return quantize(hist), compress_observations(raw, meta)


class FinalSelectionTests(unittest.TestCase):
    def test_fingerprints_equal_executed_cache_builder(self):
        frame = objects()
        expected_hist, expected_obs = frozen_features(frame)
        for free_dtype in ('Int64', 'float64'):
            frame.freeTs = frame.freeTs.astype(free_dtype)
            hist, obs = fingerprint_inputs(frame, 0, 130, 4096)
            pd.testing.assert_frame_equal(hist, expected_hist)
            pd.testing.assert_frame_equal(obs.features, expected_obs.features)
            self.assertEqual(obs.metadata, expected_obs.metadata)
        # A zero-duration allocation is in history, never in a live snapshot.
        zero = frame.iloc[:1].copy(); zero.freeTs = zero.allocTs
        self.assertTrue(fingerprint_inputs(zero, 0, 130, 4096)[1].features.empty)

    def test_selected_pages_and_memberships_equal_frozen_study_all_arms(self):
        frame = objects()
        hist, obs = frozen_features(frame)
        costs = {int(p):len(g) for p,g in frame.groupby(frame.addr//4096)}
        types = {int(p):set(g.type) for p,g in frame.groupby(frame.addr//4096)}
        for seed in (0, 3, 19):
            cs = derived_seed(seed, 'clustering')
            hl,hc = cluster_features(hist,3,cs,True)
            tl,tc = cluster_features(obs.features,3,cs,True)
            h = cluster_pages(hl,hist.index)
            t = cluster_pages(tl,[m['page'] for m in obs.metadata],6)
            for mode in MODES:
                clusters = h if mode=='no_per_time' else {**h,**t}
                centers = hc if mode=='no_per_time' else {**hc,**{c+6:v for c,v in tc.items()}}
                geom = ClusterGeometry(centers,{c:int(c>=6) for c in clusters})
                want, details = study_page_selection.select_pages(clusters,types,8,
                    forced_pages={23},page_records=costs,record_budget=28,
                    overlapping_clusters=True,cluster_geometry=geom,
                    rng=random.Random(derived_seed(seed,'selection')),
                    cluster_priority='shuffled' if mode=='no_alternation' else 'balanced50',
                    cluster_coverage_first=mode!='no_coverage_first')
                got, info, groups, _, _, _ = prepare_selection(frame,frame,0,130,4096,
                    page_budget=8,record_budget=28,seed=seed,mode=mode,forced_pages={23})
                self.assertEqual(got,want,(seed,mode))
                self.assertEqual(groups,clusters)
                for key,value in details.items(): self.assertEqual(info[key],value,key)

    def test_executed_selector_equivalence_under_random_constraints(self):
        for seed in range(100):
            rng = random.Random(seed)
            clusters = {c:sorted(rng.sample(range(25),rng.randrange(1,20))) for c in range(8)}
            types = {p:{'T'+str(p%3)} for p in range(25)}
            costs = {p:rng.randrange(1,100) for p in range(25)}
            kwargs = dict(page_records=costs,record_budget=rng.randrange(500),
                          forced_pages={seed%25},overlapping_clusters=True,
                          cluster_priority='balanced50',cluster_coverage_first=bool(seed%2),
                          cluster_geometry=ClusterGeometry({c:[c,c%3] for c in clusters}))
            expected = study_page_selection.select_pages(clusters,types,seed%16,rng=random.Random(seed),**kwargs)
            actual = select_pages(clusters,types,seed%16,rng=random.Random(seed),**kwargs)
            self.assertEqual(actual,expected)

    def test_database_entrypoint_complete_records_forced_overflow_and_cli(self):
        frame = objects()
        with tempfile.TemporaryDirectory() as td:
            db = Path(td)/'fixture.sqlite'
            with sqlite3.connect(db) as con:
                con.execute('CREATE TABLE SUPERTABLE(FILE,SIZE,ADDRESS,TYPE,TIMESTAMP,isNew,LINE,ACTUALADDR,ACTUALSIZE)')
                for r in frame.itertuples():
                    con.execute('INSERT INTO SUPERTABLE VALUES(?,?,?,?,?,?,?,?,?)',
                        (r.file,r.size,r.addr,r.type,r.allocTs,1,r.line,r.actualAddr,r.actualSize))
                    if pd.notna(r.freeTs):
                        con.execute('INSERT INTO SUPERTABLE VALUES(?,?,?,?,?,?,?,?,?)',
                            ('NULL',0,r.addr,'NULL',int(r.freeTs),0,0,r.actualAddr,0))
            sampler = Sampler(str(db))
            result = sampler.get_sample_of_pages(-1,-1,{},page_budget=8,record_budget=28,seed=3)
            self.assertLessEqual(sum(len(p['events']) for p in result['page_num_events'].values()),28)
            self.assertEqual(result['selection']['mode'],'full')
            out = Path(td)/'result.json'
            subprocess.run([sys.executable,str(ROOT/'artifact/select_pages.py'),str(db),
                            '--out',str(out),'--page-budget','8','--record-budget','28','--seed','3'],
                           check=True,capture_output=True,timeout=60)
            cli = json.loads(out.read_text())
            self.assertEqual(cli['page_num_events'],result['page_num_events'])
            # Forced pages retain all records even beyond both caps.
            sampler.get_perf_data = lambda: pd.DataFrame({'cl_addr':[23*4096]})
            forced = sampler.get_sample_of_pages(-1,-1,{},page_budget=1,record_budget=1)
            self.assertEqual(set(forced['page_num_events']),{str(23*4096)})
            self.assertEqual(len(forced['page_num_events'][str(23*4096)]['events']),len(frame[frame.addr//4096==23]))
            self.assertGreater(forced['selection']['perf_record_budget_excess'],0)

    def test_empty_and_zero_span(self):
        frame = objects().iloc[:0]
        result = prepare_selection(frame,frame,0,0,4096)
        self.assertEqual(result[0],set())
        sampler = Sampler.__new__(Sampler); sampler.num_buckets = 2000
        frame = objects().iloc[:1].copy(); frame.freeTs = frame.allocTs
        pd.testing.assert_frame_equal(sampler.get_last_object_per_bucket(frame),frame)


if __name__=='__main__': unittest.main()
