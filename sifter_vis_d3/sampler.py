import sqlite3
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
from sklearn.cluster import AgglomerativeClustering
from sklearn.cluster import MeanShift
import pandas as pd
import numpy as np
import ruptures as rpt
import matplotlib.pyplot as plt
import sys
import msgpack
import math
from random import randint


CHANGE_POINT_THRESHOLD = 10
event_labels = ['file', 'size', 'addr', 'type', 'ts', 'is_alloc']


class Sampler:

    def __init__(self, dbfile):
        self.con = sqlite3.connect(dbfile)

    def __del__(self):
        self.con.close()

    def __add_free_types(self, df):
        # alloc_type_size = {}
        df.sort_values('ts', inplace=True)
        df.loc[df["size"] == 0, "size"] = None
        df[["size", "type"]] = df.groupby("addr")[["size", "type"]].ffill()
        # for i in range(len(df)):
        #     if df.at[i, 'is_alloc'] == 1:
        #         alloc_type_size[df.at[i, 'addr']] = {'type': df.at[i, 'type'], 'size': df.at[i, 'size']}
        #     elif df.at[i, 'addr'] in alloc_type_size:
        #         df.at[i, 'type'] = alloc_type_size[df.at[i, 'addr']]['type']
        #         df.at[i, 'size'] = alloc_type_size[df.at[i, 'addr']]['size']
        #         del alloc_type_size[df.at[i, 'addr']]
        return df
    
    def get_all_records(self, page_size=4096):
        # TODO: should not need DISTINCT once memhook is fixed
        df = pd.read_sql_query("""SELECT FILE as file,
                                    SIZE as size,
                                    ADDRESS as addr,
                                    TYPE as type,
                                    TIMESTAMP as ts,
                                    isNew as is_alloc
                                FROM SUPERTABLE""",
                                self.con)
                                # dtype={'file': object,
                                #        'size': int,
                                #        'addr': int,
                                #        'type': object,
                                #        'ts': int,
                                #        'is_alloc': int})
        return df
    
    def get_all_records_and_lines(self):
        df = self.__add_free_types(self.get_all_records()).dropna(subset=['size'])
        pts = {}
        change_pts = {}
        for tp in df.loc[:, 'type'].unique():
            type_df_alloc = df[(df['type'] == tp) & (df['is_alloc'] == 1)][['ts', 'size']]
            type_df_free = df[(df['type'] == tp) & (df['is_alloc'] == 0)][['ts', 'size']]
            type_df_free['size'] = type_df_free['size'] * -1
            # TODO: should confirm that this method of sorting works as expected
            df_pts = type_df_alloc.merge(type_df_free, how='outer', sort=True).set_index('ts').cumsum()
            pts[tp] = [{'ts': int(rec[0]), 'size': int(rec[1])} for rec in zip(df_pts.index.to_list(), df_pts['size'])]
            if len(df[df['type'] == tp]) >= CHANGE_POINT_THRESHOLD:
                change_point_alg = rpt.Window(width=150, model='l2', min_size=CHANGE_POINT_THRESHOLD).fit(df_pts)
                change_pts[tp] = list(map(int, change_point_alg.predict(pen=20)))

        return {'records': df.to_dict(orient='records'), 'pts': pts, 'changes': change_pts}

    def get_records_in_interval(self, start_ts, end_ts, page_size=4096):
        # TODO: change this to get alloc events before start if matching free is after start
        df = pd.read_sql_query("""SELECT FILE as file,
                                    SIZE as size,
                                    ADDRESS as addr,
                                    TYPE as type,
                                    TIMESTAMP as ts,
                                    isNew as is_alloc
                                FROM SUPERTABLE
                                WHERE ts>=? AND ts<=?""", self.con, params=(start_ts, end_ts))
        return df

    def get_clusters_of_pages(self, start_ts, end_ts, page_size=4096, alg='dbscan'):
        recs = self.get_records_in_interval(start_ts, end_ts, page_size) if start_ts > 0 and end_ts > 0 else self.get_all_records()
        df = self.__add_free_types(recs).dropna(subset=['size'])
        df['page_num'] = df['addr'] // page_size

        if len(df) == 0:
            return pd.DataFrame(dict())

        allocs = df[df['is_alloc'] == 1]
        frees = df[df['is_alloc'] == 0]

        pivot_allocs = pd.pivot_table(allocs, values='is_alloc', index='page_num',
                                        columns='type', aggfunc='count', fill_value=0)
        pivot_frees = pd.pivot_table(frees, values='is_alloc', index='page_num',
                                        columns='type', aggfunc='count', fill_value=0)
        
        merged = pivot_allocs.merge(pivot_frees, how='left', on='page_num', suffixes=('_alloc', '_free')).fillna(value=0)
        # print(merged)
        #TODO Take a look at FeatureAgglomeration?
        page_pattern = StandardScaler().fit_transform(merged)
        clusters = None
        if (alg == 'dbscan'):
            clusters = DBSCAN(eps=0.6, min_samples=max(1, math.floor(len(merged.index) / 150))).fit_predict(page_pattern)
        elif (alg == 'agglomerative'):
            clusters = AgglomerativeClustering(n_clusters=None, distance_threshold=10).fit_predict(page_pattern)
        elif (alg == 'meanshift'):
            clusters = MeanShift(min_bin_freq=math.floor(len(merged.index) / 150), cluster_all=False).fit_predict(page_pattern)
        merged['cluster'] = clusters
        
        pages = pd.DataFrame.from_dict({page: [group[event_labels].values.tolist()]
                    for page, group in df.groupby('page_num')}, orient='index')
        pages.index.name = 'page_num'
        labeled = pages.merge(merged.loc[:, 'cluster'], on='page_num')

        return labeled

    def get_sample_of_pages(self, start_ts, end_ts, page_size=4096, cluster_alg='dbscan', 
                            max_run_length=3, max_runs_from_cluster=2, include_all_noise=True):
        labeled_data = self.get_clusters_of_pages(start_ts, end_ts, page_size, alg=cluster_alg)
        clusters = labeled_data.groupby('cluster', sort=False).groups
        # print(clusters)
        # print("Number of clusters: {}".format(len(clusters)))
        sampled_pages = set()
        for c in clusters:
            if len(clusters[c]) <= max_runs_from_cluster * max_run_length:
                sampled_pages.update(clusters[c])
            else:
                for _ in range(max_runs_from_cluster):
                    start = randint(0, len(clusters[c]) - 1)
                    sampled_pages.add(clusters[c][start])
                    num_s = 1
                    while start + num_s < len(clusters[c]) and clusters[c][start + num_s] == clusters[c][start + num_s - 1] + 1 and num_s < max_run_length:
                        sampled_pages.add(clusters[c][start + num_s])
                        num_s += 1
        
        sampled_pages_df = pd.DataFrame({'page_num': sorted(sampled_pages)})
        merged = sampled_pages_df.merge(labeled_data, how='left', on='page_num')
        dict_merged = merged.set_index('page_num').set_axis(['events', 'cluster'], axis='columns').to_dict(orient='index')
        return {pn: {'events': [dict(zip(event_labels, event)) for event in v['events']], 'cluster': v['cluster']} for pn, v in dict_merged.items()}


if __name__ == "__main__":
    # pd.set_option('display.max_columns', None)
    pd.options.mode.chained_assignment = None
    s = Sampler(sys.argv[2])
    retval = None

    if sys.argv[1] == "all":
        retval = s.get_all_records_and_lines();
        # print(retval)
    else:
        retval = s.get_sample_of_pages(int(sys.argv[3]), int(sys.argv[4]), cluster_alg=sys.argv[5],
                                       max_run_length=int(sys.argv[6]), max_runs_from_cluster=int(sys.argv[7]))    

    print(msgpack.packb(retval['pts'], use_bin_type=True))
    sys.stdout.flush()

# abtree_ns::Node<11,longlong>_alloc
# KeyGeneratorUniform<longlong> 34230449716 34230449754