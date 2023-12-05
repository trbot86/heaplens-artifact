import sqlite3
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
import pandas as pd
import sys
import json
from random import randint


event_labels = ['file', 'size', 'addr', 'type', 'ts', 'is_alloc']


class Sampler:

    def __init__(self, dbfile):
        self.con = sqlite3.connect(dbfile)

    def __del__(self):
        self.con.close()

    def __add_free_types(self, df):
        alloc_type = dict()
        df.sort_values('ts', inplace=True)
        for i in range(len(df)):
            if df.at[i, 'is_alloc'] == 1:
                alloc_type[df.at[i, 'addr']] = df.at[i, 'type']
            elif df.at[i, 'addr'] in alloc_type:
                df.at[i, 'type'] = alloc_type[df.at[i, 'addr']]
                del alloc_type[df.at[i, 'addr']]
        return df

    def get_records_in_interval(self, start_ts, end_ts, page_size=4096):
        df = pd.read_sql_query("""SELECT DISTINCT FILE as file,
                                    SIZE as size,
                                    ADDRESS as addr,
                                    TYPE as type,
                                    TIMESTAMP as ts,
                                    isNew as is_alloc
                                FROM SUPERTABLE
                                WHERE ts>=? AND ts<=?""", self.con, params=(start_ts, end_ts))
        df['page_num'] = df['addr'] // page_size
        return df

    def get_clusters_of_pages(self, start_ts, end_ts, page_size=4096):
        df = self.__add_free_types(self.get_records_in_interval(start_ts, end_ts, page_size))

        if len(df) == 0:
            return pd.DataFrame(dict())

        allocs = df[df['is_alloc'] == 1]
        frees = df[df['is_alloc'] == 0]

        pivot_allocs = pd.pivot_table(allocs, values='is_alloc', index='page_num',
                                        columns='type', aggfunc='count', fill_value=0)
        pivot_frees = pd.pivot_table(frees, values='is_alloc', index='page_num',
                                        columns='type', aggfunc='count', fill_value=0)
        
        merged = pivot_allocs.merge(pivot_frees, on='page_num', suffixes=('_alloc', '_free'))      
        page_pattern = StandardScaler().fit_transform(merged)
        clusters = DBSCAN(eps=0.2, min_samples=2).fit_predict(page_pattern)
        merged['cluster'] = clusters
        
        pages = pd.DataFrame.from_dict({page: [group[event_labels].values.tolist()]
                    for page, group in df.groupby('page_num')}, orient='index')
        pages.index.name = 'page_num'
        labeled = pages.merge(merged.loc[:, 'cluster'], on='page_num')

        return labeled

    def get_sample_of_pages(self, start_ts, end_ts, page_size=4096, 
                            max_run_length=3, max_runs_from_cluster=2, include_all_noise=True):
        labeled_data = self.get_clusters_of_pages(start_ts, end_ts, page_size)
        clusters = labeled_data.groupby('cluster', sort=False).groups
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
    s = Sampler("allocs.sqlite")
    retval = None

    if sys.argv[1] == "all":
        retval = s.get_all_records();
    else:
        retval = s.get_sample_of_pages(1480657570462, 1481102748072)
    # print([sample[page]['cluster'] for page in sorted(sample.keys())])
    print(json.dumps(retval))
    sys.stdout.flush()

# abtree_ns::Node<11,longlong>_alloc