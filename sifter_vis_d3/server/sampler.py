import sqlite3
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import MiniBatchKMeans
from sklearn.cluster import KMeans
from sklearn.cluster import DBSCAN
from sklearn.cluster import AgglomerativeClustering
from sklearn.cluster import MeanShift
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
import math
import os
from random import randint, shuffle

MAX_PAGE_PROP = 7560
MAX_OBJ_STATS = 1000000
CHANGE_POINT_THRESHOLD = 10
event_labels = ['file', 'size', 'addr', 'type', 'allocTs', 'freeTs', 'line']

FILE_IND = 0
SIZE_IND = 1
ADDR_IND = 2
TYPE_IND = 3
ALLOC_TS_IND = 4
FREE_TS_IND = 5
TYPE_KIND_IND = 6
LINE_IND = 7

def replace_nan(event, key):
    if math.isnan(event[key]):
        event[key] = None
    return event

def get_sub_tname(t, st):
    return ">" + t.replace(' ', '') + "|" + st

def get_bucket(min_ts, max_ts, num_buckets, ts):
    size_of_bucket = max(math.floor(max_ts - min_ts) / num_buckets, 1)
    return math.ceil((ts - min_ts) / size_of_bucket)


class Sampler:

    def __init__(self, dbfile, page_size=4096, cache_line_size=64, num_buckets=2000):
        self.fname = dbfile
        self.all_data = self.get_all_records(page_size)
        self.min_ts = int(self.all_data["ts"].min())
        self.max_ts = int(self.all_data["ts"].max())
        self.page_size = page_size
        self.cache_line_size = cache_line_size
        self.num_buckets = num_buckets

    def __del__(self):
        return

    def add_free_types(self, df):
        df.sort_values('ts', inplace=True)
        df.loc[(df["file"] == "NULL") | (df["size"] == 0) | (df["type"] =="NULL"),["file", "size", "type"]] = None, None, None
        # df.loc[df["size"] == 0,"size"] = None
        # df.loc[df["type"] == "NULL","type"] = None
        # grouped = df.groupby("addr")
        df.loc[:,["file","size","type"]] = df.groupby("addr")[["file", "size", "type"]].ffill(limit=1)
        # df.loc[:,"size"] = grouped["size"].ffill(limit=1)
        # df.loc[:,"type"] = grouped["type"].ffill(limit=1)
        return df
    
    def get_objects(self, df):
        # Duplicate ts into allocTs and freeTs
        df = self.add_free_types(df)
        df = df.rename(columns={"ts": "allocTs"})
        df.loc[:,"freeTs"] = df.loc[:,"allocTs"]

        # Change freeTs of all allocs to None
        df.loc[df["is_alloc"] == 1,"freeTs"] = None

        # Fill in the freeTs of each alloc with freeTs of soonest free
        df.loc[:,"freeTs"] = df.groupby("addr")["freeTs"].bfill(limit=1)

        # Get rid of the old frees and drop the is_alloc column
        df = df.loc[df["is_alloc"] == 1,:].drop(columns=["is_alloc"]).dropna(subset=["allocTs", "type"])

        # The following is a bit of a hack to deal with placement new.
        # For all of the remaining objects that have no free timestamp,
        # we fill the free timestamp with the next allocation timestamp
        # with the same address and type. (NOTE: this keeps overlapping
        # objects with distinct types)
        # df.loc[df["freeTs"].isnull(),"freeTs"] = df.groupby(["addr", "type"])["allocTs"].shift(periods=-1).dropna()
        # return df.iloc[:,[]]
        return df.iloc[:,[0, 1, 2, 3, 4, 6, 5]]
    
    def get_all_lines(self):
        con = sqlite3.connect(self.fname)
        df = pd.read_sql_query("""SELECT TYPE as type,
                                    BUCKET as bucket,
                                    SIZE as size
                                FROM LINES""",
                                con)
        return df

    def get_all_records(self, page_size=4096):
        con = sqlite3.connect(self.fname)
        dfs = []
        i = 0
        for chunk in pd.read_sql_query("""SELECT FILE as file,
                                    SIZE as size,
                                    ADDRESS as addr,
                                    TYPE as type,
                                    TIMESTAMP as ts,
                                    isNew as is_alloc,
                                    LINE as line
                                FROM SUPERTABLE""",
                                con,
                                chunksize=100000):
            chunk.index = pd.RangeIndex(start=i*100000, stop=i*100000 + len(chunk), step=1)
            dfs.append(chunk)
            i += 1
        con.close()
        return pd.concat(dfs)
    
    def types(self):
        return [tp for tp in self.all_data['type'].unique().tolist() if isinstance(tp, str)]
    
    def get_counts(self):
        try:
            con = sqlite3.connect(self.fname)
            df = pd.read_sql_query("""SELECT TYPE as type,
                                        ALLOCS as numAllocs,
                                        PAGES as numPages
                                    FROM STATS""",
                                    con)
            con.close()
            return df
        except:
            return pd.DataFrame(columns=['type', 'numAllocs', 'numPages'])
    
    def get_stats(self, recs, cls=64):
        objs = self.get_objects(recs)

        # Get the CL address of the beginning of each object
        cl_begin = objs.loc[:,['addr', 'type', 'allocTs', 'freeTs']]
        cl_begin.loc[:,'addr'] = cl_begin.loc[:,'addr'] // cls

        # Get the CL address of the end of each object (subtract 1 to deal with case when divisible by cls)
        cl_end = objs.loc[:,['type', 'allocTs', 'freeTs']]
        cl_end.loc[:,'addr'] = ((objs.loc[:,'addr'] + objs.loc[:,'size']) - 1) // cls

        # Get rid of duplicates (i.e. objects that start and end in same CL)
        merged = cl_begin.merge(cl_end, how='outer')
        allocs = merged.loc[:,['type', 'allocTs', 'addr']]
        allocs.loc[:,['is_alloc']] = True
        allocs = allocs.rename(columns={'allocTs': 'ts'})
        frees = merged.loc[:,['type', 'freeTs', 'addr']]
        frees.loc[:,['is_alloc']] = False
        frees = frees.rename(columns={'freeTs': 'ts'})
        allrecs = pd.concat([allocs, frees]).sort_values('ts').dropna(subset=['addr'])
        allrecs.loc[:,'addr'] = allrecs.loc[:,'addr'].astype('Int64')

        retval = {'total': merged.groupby('type')['addr'].count().to_dict()}

        TYPE_IND = 0
        TS_IND = 1
        ADDR_IND = 2
        IS_ALLOC_IND = 3
        cl_current = {}
        alltypes = merged['type'].unique()
        coloc = {tp1: {tp2: 0 for tp2 in alltypes} for tp1 in alltypes}
        for rec in allrecs.values.tolist():
            if rec[IS_ALLOC_IND]:
                if not rec[ADDR_IND] in cl_current:
                    cl_current[rec[ADDR_IND]] = {tp: 0 for tp in alltypes}
                
                for tp in alltypes:
                    if cl_current[rec[ADDR_IND]][tp] > 0:
                        coloc[rec[TYPE_IND]][tp] += 1
                        coloc[tp][rec[TYPE_IND]] += 1
                cl_current[rec[ADDR_IND]][rec[TYPE_IND]] += 1
            else:
                print(rec)
                cl_current[rec[ADDR_IND]][rec[TYPE_IND]] -= 1

        retval['coloc'] = coloc
        return retval
        
        # cl_groups = allrecs.groupby('addr')
        # alltypes = merged['type'].unique()
        # zero_data = np.zeros(shape=(len(alltypes), len(alltypes)))
        # coloc = pd.DataFrame(zero_data, index=alltypes, columns=alltypes).astype(int)
        # j = 0
        # for gp in cl_groups.groups:
        #     j += 1
        #     if j % 1000 == 0:
        #         print(j)
        #     cl = cl_groups.get_group(gp)

        #     current = pd.DataFrame(np.zeros(shape=(len(alltypes), 1)), index=alltypes, columns=['count']).astype(int)
        #     for i, data in cl.iterrows():
        #         if data['is_alloc']:
        #             coloc.loc[current[current['count'] > 0].index,[data['type']]] += 1
        #             coloc.loc[[data['type']],current[current['count'] > 0].index] += 1
        #             current.loc[data['type'],:] += 1
        #         else:
        #             current.loc[data['type'],:] -= 1

        # retval['coloc'] = coloc.to_dict()
        # return retval
        # for tp in merged['type'].unique():
        #     # print("Getting stats for {}".format(tp))
        #     tp_objs = merged[merged['type'] == tp]
        #     addr_other_objs = merged[(merged['type'] != tp) & (merged['addr'].isin(tp_objs['addr']))]
        #     allTs = pd.concat([tp_objs['allocTs'], addr_other_objs['allocTs']])
        #     min_ts = allTs.min()
        #     max_ts = allTs.max()
        #     while len(tp_objs.index) * len(addr_other_objs.index) > MAX_OBJ_STATS:
        #         max_ts = (min_ts + max_ts) // 2
        #         tp_objs = merged[(merged['allocTs'] <= max_ts) & (merged['type'] == tp)]
        #         addr_other_objs = merged[(merged['allocTs'] <= max_ts) & (merged['type'] != tp) & (merged['addr'].isin(tp_objs['addr']))]
            
        #     # Get all pairs of events, and filter to pick ones that overlap in time, with the same CL address,
        #     # and different allocTs (this is just a hack to prevent an event from matching with itself)
        #     cross = tp_objs.drop(columns=['type']).merge(addr_other_objs, how='cross', suffixes=('_me', '_other'))
        #     filtered = cross[(cross['allocTs_me'] <= cross['freeTs_other']) & \
        #                     (cross['freeTs_me'] >= cross['allocTs_other']) & \
        #                     (cross['allocTs_me'] != cross['allocTs_other']) & \
        #                     (cross['addr_me'] == cross['addr_other'])]
            
        #     # For each type, count all of the other objects with the same CL address
        #     counts = filtered.groupby(['addr_me','type'])['allocTs_me'].count().reset_index().rename(columns={'allocTs_me': 'count'})

        #     while len(tp_objs.index) > math.sqrt(MAX_OBJ_STATS):
        #         max_ts = (min_ts + max_ts) // 2
        #         tp_objs = merged[(merged['allocTs'] <= max_ts) & (merged['type'] == tp)]

        #     mask_my_type = (
        #         (tp_objs[(tp_objs['allocTs'] <= max_ts)]['allocTs'].values.reshape(-1, 1) <= tp_objs[(tp_objs['allocTs'] <= max_ts)]['freeTs'].values.reshape(1, -1)) &
        #         (tp_objs[(tp_objs['allocTs'] <= max_ts)]['freeTs'].values.reshape(-1, 1) >= tp_objs[(tp_objs['allocTs'] <= max_ts)]['allocTs'].values.reshape(1, -1)) &
        #         (tp_objs[(tp_objs['allocTs'] <= max_ts)]['addr'].values.reshape(-1, 1) == tp_objs[(tp_objs['allocTs'] <= max_ts)]['addr'].values.reshape(1, -1)) &
        #         (pd.RangeIndex(len(tp_objs)) < pd.RangeIndex(len(tp_objs)).to_numpy().reshape(-1, 1))
        #     )
            
        #     # Sum over all of the addresses for each type
        #     retval['coloc'][tp] = counts.drop(columns=['addr_me']).groupby(['type']).sum().to_dict()['count']
        #     retval['coloc'][tp][tp] = np.count_nonzero(mask_my_type) * 2

        # return retval
        # # Turn everything into a dict to return
        # # return {'total': merged.groupby('type')['addr'].count().to_dict(),
        # #         'coloc': {k: {pair[1]: v['count'] for pair, v in g.to_dict(orient='index').items()} for k, g in sums.groupby(level=0)}}
        
    def get_last_object_per_bucket(self, df):
        min_ts = df[['allocTs', 'freeTs']].min().min()
        max_ts = df[['allocTs', 'freeTs']].max().max()
        bucket_size = (max_ts - min_ts) / self.num_buckets
        df.loc[:,'bucket'] = ((df['allocTs'] - min_ts) // bucket_size).astype('Int64')

        last_allocs = df.groupby(['addr', 'type', 'bucket']).agg({'allocTs': 'last'})
        last_allocs = last_allocs.merge(df, how='left', on=['addr', 'type', 'allocTs'])
        return last_allocs
    
    def get_all_lines_and_stats(self):
        # recs = self.all_data
        # df = self.add_free_types(recs).dropna(subset=['file','size','type'])

        # bucket_size = (max_ts - min_ts) / self.num_buckets
        # df.loc[:,'bucket'] = ((df.loc[:,'ts'] - min_ts) // bucket_size).astype('Int64')

        # # print(df)
        # pts = {}
        # change_pts = {}
        # for tp in df.loc[:, 'type'].unique():
        #     type_df_alloc = df[(df['type'] == tp) & (df['is_alloc'] == 1)][['ts', 'addr', 'size', 'bucket']]
        #     type_df_free = df[(df['type'] == tp) & (df['is_alloc'] == 0)][['ts', 'addr', 'size', 'bucket']]
        #     type_df_free['size'] = type_df_free['size'] * -1
        #     # type_df_alloc.rename(columns={'allocTs': 'ts'}, inplace=True)
        #     # type_df_free.rename(columns={'freeTs': 'ts'}, inplace=True)
        #     merged = type_df_alloc.merge(type_df_free, how='outer', sort=True)
        #     sum_allocs = merged.groupby(['addr', 'bucket']).agg({'size': 'sum', 'ts': 'last'}).sort_values('ts')

        #     df_pts = sum_allocs.set_index('ts').cumsum()
        #     pts[tp] = [{'ts': int(rec[0]), 'size': int(rec[1])} for rec in zip(df_pts.index.to_list(), df_pts['size'])]
        #     # if len(df[df['type'] == tp]) >= CHANGE_POINT_THRESHOLD:
        #     #     change_point_alg = rpt.Window(width=150, model='l2', min_size=CHANGE_POINT_THRESHOLD).fit(df_pts)
        #     #     change_pts[tp] = list(map(int, change_point_alg.predict(pen=20)))

        # # objects = self.get_objects(recs) if len(recs.index) < 2000000 else self.get_last_object_per_bucket(self.get_objects(recs), self.num_buckets).drop(columns=['bucket'])

        # # print(f"cols in objects: {self.get_objects(recs).columns}")
        # # print(f"cols in objects: {objects.columns}")

        lines_df = self.get_all_lines()
        num_line_pts_x = lines_df["bucket"].max()
        line_pts = dict()
        for entry in self.get_all_lines().values.tolist():
            if not entry[0] in line_pts:
                line_pts[entry[0]] = [0]*(num_line_pts_x+1)
            line_pts[entry[0]][entry[1]] = {"bucket": entry[1], "size": entry[2]}

        print("Returning from get_all_lines_and_stats")

        return {'pts': line_pts,
                'changes': {},
                'stats': {},#{'single': self.get_stats(recs, self.cache_line_size), 'double': self.get_stats(recs, 2*self.cache_line_size)},
                'fields': self.get_fields(s.replace(' ', '') for s in lines_df['type'].unique()),
                'counts': self.get_counts().set_index('type').to_dict('index'),
                'perf': self.get_perf_data().drop_duplicates(subset=['cl_addr']).set_index('cl_addr').to_dict(orient='index'),
                'minTs': self.min_ts,
                'maxTs': self.max_ts}
        # 'records': df.to_dict(orient='records'), 

    def get_records_in_interval(self, start_ts, end_ts, page_size=4096):
        con = sqlite3.connect(self.fname)
        df = pd.read_sql_query("""SELECT FILE as file,
                                    SIZE as size,
                                    ADDRESS as addr,
                                    TYPE as type,
                                    TIMESTAMP as ts,
                                    isNew as is_alloc,
                                    LINE as line
                                FROM SUPERTABLE
                                WHERE is_alloc=0 OR (ts <= {} AND is_alloc=1)""".format(end_ts),
                                con)
                                # dtype={'file': object,
                                #        'size': int,
                                #        'addr': int,
                                #        'type': object,
                                #        'ts': int,
                                #        'is_alloc': int})
        con.close()
        return df
        # TODO: change this to get alloc events before start if matching free is after start
        # TODO: just send the objects themselves, not individual allocs & frees
        # TODO: sort into page nums as well
    
    def get_perf_data(self):
        try:
            con = sqlite3.connect(self.fname)
            df = pd.read_sql_query("""SELECT CLADDRESS as cl_addr,
                                        HITM as hitm
                                    FROM PERF""",
                                    con)
            con.close()
            return df
        except:
            return pd.DataFrame({"cl_addr": [], "hitm": []})

    def get_fields(self, types):
        try:
            con = sqlite3.connect(self.fname)
            df = pd.read_sql_query("""SELECT TYPE as type,
                                        SUBTYPE as subtype,
                                        NAME as name,
                                        SIZE as size,
                                        OFFSET as offset
                                    FROM FIELDS""",
                                    con)
            con.close()
            return {k: v.to_dict(orient='records') for k, v in df[df['type'].isin(types)].set_index('type').groupby(level=0)}
        except:
            return dict()

    def get_clusters_of_pages(self, start_ts, end_ts, type_data, alg='dbscan'):
        # recs = self.get_records_in_interval(start_ts, end_ts, page_size) if start_ts > 0 and end_ts > 0 else self.get_all_records()
        recs = self.all_data
        # df = self.__add_free_types(recs).dropna(subset=['size'])
        df = self.get_objects(recs)
        df = df.drop(df[df['freeTs'] < start_ts].index)
        df.loc[:,'page_num'] = df.loc[:,'addr'] // self.page_size

        perf_df = self.get_perf_data()
        perf_df.loc[:,'page_num'] = perf_df.loc[:,'cl_addr'] // self.page_size

        filter_types = pd.DataFrame({'type': list(type_data.keys()), 'mask': list(type_data.values())})
        type_entries = df.merge(filter_types, how='left', on='type')
        type_entries.loc[:,'mask'] = type_entries.loc[:,'mask'].astype(object)
        type_entries.loc[type_entries['page_num'].isin(perf_df['page_num']),'mask'] = True
        type_entries.loc[:,'mask'] = type_entries.loc[:,'mask'].fillna(True).astype(bool)
        pages_to_keep = type_entries[type_entries['mask']]['page_num']
        df = df[df['page_num'].isin(pages_to_keep)]

        last_allocs = self.get_last_object_per_bucket(df)

        # last_allocs.loc[:,'page_num'] = last_allocs.loc[:,'addr'] // page_size
        # df.loc[:,'page_num'] = df.loc[:,'addr'] // page_size

        if len(last_allocs) == 0:
            return pd.DataFrame(dict())
        
        # allocs = df[df['allocTs'] >= start_ts] if start_ts >= 0 else df.dropna(subset=["allocTs"])
        # frees = df[df['freeTs'] <= end_ts] if end_ts >= 0 else df.dropna(subset=["freeTs"])

        # CHANGED is_alloc to addr BELOW
        # pivot_allocs = pd.pivot_table(allocs, values='addr', index='page_num',
        #                                 columns='type', aggfunc='count', fill_value=0)
        # pivot_frees = pd.pivot_table(frees, values='addr', index='page_num',
        #                                 columns='type', aggfunc='count', fill_value=0)
        
        # merged = pivot_allocs.merge(pivot_frees, how='left', on='page_num', suffixes=('_alloc', '_free')).fillna(value=0)

        # Add the double cacheline alignment to each row
        df.loc[:,'align'] = df.loc[:,'addr'] % (2*self.cache_line_size)
        # For each page, type, and alignment, count the number of objects of that type at that alignment in that page
        grouped = df.groupby(['page_num', 'type', 'align'])['size'].count()
        # Rename the 'size' column to 'count'
        grouped.name = 'count'
        # Get rid of the hierarchical indices
        grouped = grouped.reset_index(['page_num', 'type', 'align']).set_index('page_num')
        
        # Put each (type, alignment) pair into its own column
        pivot_align = grouped.pivot_table(index='page_num', columns=['type', 'align'], values='count', fill_value=0)
        # Get the max count of each (type, alignment) across all pages
        maxes = grouped.groupby(['type','align'])['count'].max().reset_index() \
            .pivot_table(columns=['type','align'], values='count', fill_value=0)
        # Scale each (type, alignment) count to a number between 0 and 3
        scaled = (pivot_align / maxes.loc['count',:])*3
        # Create mask for entries between 0 and 1
        mask = (scaled > 0) & (scaled < 1)
        # Round all of the entries between 0 and 1 up to 1, otherwise take the floor
        clamped = np.floor(scaled.mask(mask, other=1))
        # Flatten all of the multilevel columns
        clamped.columns = [' '.join(map(str, col)).strip() for col in clamped.columns]

        merged = clamped
        # merged = merged.merge(clamped, how='left', on='page_num').fillna(value=0)

        print("About to start clustering pages")

        #TODO Take a look at FeatureAgglomeration?
        page_pattern = StandardScaler().fit_transform(merged)
        clusters = None
        if (len(merged.index) <= 1):
            clusters = [0]
        elif (alg == 'mbkmeans'):
            clusters = MiniBatchKMeans(n_clusters=min(2*len(self.types()), len(merged.index))).fit_predict(page_pattern)
        elif (alg == 'kmeans'):
            clusters = KMeans(n_clusters=min(2*len(self.types()), len(merged.index))).fit_predict(page_pattern)
        elif (alg == 'dbscan'):
            clusters = DBSCAN(eps=0.9, min_samples=1).fit_predict(page_pattern)
        elif (alg == 'agglomerative'):
            clusters = AgglomerativeClustering(n_clusters=None, distance_threshold=10).fit_predict(page_pattern)
        elif (alg == 'meanshift'):
            clusters = MeanShift(min_bin_freq=1, cluster_all=False).fit_predict(page_pattern)
        merged['cluster'] = clusters

        print("Done clustering pages")
        
        pages = pd.DataFrame.from_dict({page: [group[event_labels].values.tolist()]
                    for page, group in last_allocs.groupby('page_num')}, orient='index')
        pages.index.name = 'page_num'
        labeled = pages.merge(merged.loc[:,'cluster'], on='page_num')
        # labeled = pages
        # merged['cluster'] = 0
        # labeled['cluster'] = 0

        return labeled, merged, perf_df

    def get_sample_of_pages(self, start_ts, end_ts, type_data, cluster_alg='dbscan', 
                            max_run_length=3, max_runs_from_cluster=2, include_all_noise=True):
        labeled_data, features, perf_df = self.get_clusters_of_pages(start_ts, end_ts, type_data, alg=cluster_alg)
        # .reset_index().set_index('cluster')
        clusters = labeled_data.groupby('cluster', sort=False).groups

        max_pages = math.floor(MAX_PAGE_PROP / pow(math.log(self.page_size, 2), 2))
        # max_pages = 1 # DEBUGGING
        sampled_pages = set(perf_df[perf_df['page_num'].isin(labeled_data.index)]['page_num'].tolist())
        # sampled_pages.add(34127647253)
        # sampled_pages.add(0x7f028df4e000 // 4096)
        
        taken = 0
        cluster_keys = list(clusters.keys())
        shuffle(cluster_keys)
        for c in cluster_keys:
            if taken >= max_pages:
                break
            if len(clusters[c]) <= max_runs_from_cluster * max_run_length:
                sampled_pages.update(clusters[c])
                taken += len(clusters[c])
            else:
                for _ in range(max_runs_from_cluster):
                    start = randint(0, len(clusters[c]) - 1)
                    sampled_pages.add(clusters[c][start])
                    num_s = 1
                    while start + num_s < len(clusters[c]) and clusters[c][start + num_s] == clusters[c][start + num_s - 1] + 1 and num_s < max_run_length:
                        sampled_pages.add(clusters[c][start + num_s])
                        num_s += 1
                    taken += num_s
        # print(sampled_pages)
        
        sampled_pages_df = pd.DataFrame({'page_num': sorted(sampled_pages)})
        features = sampled_pages_df.merge(features, how='left', on='page_num')
        merged = sampled_pages_df.merge(labeled_data, how='left', on='page_num')
        
        all_merged = merged.set_index('page_num').set_axis(['events', 'cluster'], axis='columns')
        dict_merged = all_merged.to_dict(orient='index')
        fts = event_labels.index("freeTs")

        # print("BLAH BLAH BLAH")
        # print(all_merged)

        # for pn, v in dict_merged.items():
        #     print("HERE ARE THE EVENTS FOR PAGE {}:".format(pn))
        #     print(v['events'])
        #     for event in v['events']:
        #         print("\t{}".format(dict(zip(event_labels, replace_nan(event, fts)))))

        cluster_pages = features.reset_index().loc[:,['cluster','page_num']].groupby('cluster').agg(lambda x: x.tolist()).to_dict(orient='index')
        cluster_sizes = {c: len(clusters[c]) for c in cluster_pages.keys()}

        return {'page_num_events': {f"{pn*self.page_size}": {'events': [dict(zip(event_labels, replace_nan(event, fts))) for event in v['events']], 'cluster': v['cluster']} for pn, v in dict_merged.items()},
                'clusters': {c: {'pages': cluster_pages[c], 'size': cluster_sizes[c]} for c in cluster_pages.keys()},
                'sum_cluster_sizes': sum([len(clusters[c]) for c in clusters.keys()]),
                'num_clusters': len(clusters.keys()),
                'features': {pn: {tp: int(val) for tp, val in v.items() if val > 0} for pn, v in features.set_index('page_num').drop(columns=['cluster']).to_dict(orient='index').items()}}
    
    def get_cache_data(self, size, assoc):
        pd.options.display.float_format = '{:.0f}'.format
        num_cache_sets = size // (assoc * self.cache_line_size)
        all_objs = self.get_objects(self.all_data)
        # free_ts_is_na = all_objs.loc[all_objs["freeTs"].isna()]
        # free_ts_is_not_na = all_objs.loc[all_objs["freeTs"].notna()]
        # print(free_ts_is_not_na.loc[free_ts_is_not_na["type"] == "leanstore::storage::btree::BTreeVI::ChainedTuple"])
        # print(free_ts_is_na.loc[free_ts_is_na["type"] == "leanstore::storage::btree::BTreeVI::ChainedTuple"])
        # print(all_objs.columns)
        rows = all_objs.to_numpy()
        types = self.types()
        fields = self.get_fields([s.replace(' ', '') for s in types])
        i = 0
        tp_and_st_in_order = []
        tp_and_st_to_idx = dict()
        for tp in types:
            tp_and_st_in_order.append(tp)
            tp_and_st_to_idx[tp] = i
            i += 1
            if tp.replace(' ', '') in fields:
            # if tp == "block<Node<long long, void*> >" or tp == "node_t":
                for st in fields[tp.replace(' ', '')]:
                    tp_and_st_in_order.append(get_sub_tname(tp, st["subtype"]))
                    tp_and_st_to_idx[get_sub_tname(tp, st["subtype"])] = i
                    i += 1

        data = np.empty(shape=(self.num_buckets + 2, num_cache_sets, len(tp_and_st_in_order)))
        data.fill(0)

        for obj in rows:
            entries = [obj]
            if obj[TYPE_IND].replace(' ', '') in fields: #and (obj[TYPE_IND] == "block<Node<long long, void*> >" or tp == "node_t"):
                for field_ent in fields[obj[TYPE_IND].replace(' ', '')]:
                    entries.append([obj[FILE_IND],
                                    field_ent["size"],
                                    obj[ADDR_IND] + field_ent["offset"],
                                    get_sub_tname(obj[TYPE_IND].replace(' ', ''), field_ent["subtype"]),
                                    obj[ALLOC_TS_IND],
                                    obj[FREE_TS_IND]])
            for entry in entries:
                start_set = math.floor(entry[ADDR_IND] / self.cache_line_size) % num_cache_sets
                rem_size = entry[SIZE_IND] - (self.cache_line_size - (entry[ADDR_IND] % self.cache_line_size))
                alloc_time_bucket = get_bucket(self.min_ts, self.max_ts, self.num_buckets, entry[ALLOC_TS_IND])
                free_time_bucket = -1 if math.isnan(entry[FREE_TS_IND]) else get_bucket(self.min_ts, self.max_ts, self.num_buckets, entry[FREE_TS_IND])
                # if entry[TYPE_IND] == "leanstore::storage::btree::BTreeVI::ChainedTuple":
                #     print("alloc bucket: {}, free bucket: {}".format(alloc_time_bucket, free_time_bucket))
                try:
                    data[alloc_time_bucket,start_set,tp_and_st_to_idx[entry[TYPE_IND]]] += 1
                    if free_time_bucket >= 0:
                        data[free_time_bucket,start_set,tp_and_st_to_idx[entry[TYPE_IND]]] -= 1
                    i = 1
                    while rem_size > 0 and i <= num_cache_sets:
                        data[alloc_time_bucket,(start_set + i) % num_cache_sets,tp_and_st_to_idx[entry[TYPE_IND]]] += 1
                        if free_time_bucket >= 0:
                            data[free_time_bucket,(start_set + i) % num_cache_sets,tp_and_st_to_idx[entry[TYPE_IND]]] -= 1
                        rem_size -= self.cache_line_size
                        i += 1
                except KeyError:
                    print('KEY ERROR!!!')
                    print(tp_and_st_to_idx)
                    print(entry)

        # flatten the data matrix to 2d
        flat = np.array(data).reshape(len(data), -1)
        row_idx = pd.Index(range(len(data)), name="time_bucket")
        col_idx = pd.MultiIndex.from_product(
            [range(len(data[0])), range(len(data[0][0]))],
            names=["cache_set", "type_idx"]
        )

        df = pd.DataFrame(flat, index=row_idx, columns=col_idx)
        df = df.cumsum()

        print("Returning from get_cache_data")

        return {
            "occ": df.values.astype(int).tolist(),
            "idxToTpAndSt": tp_and_st_in_order,
            "numSets": num_cache_sets
        }
        # return None


if __name__ == "__main__":
    s = Sampler("../tpcc_bronson_n8.sqlite")
    print(s.get_cache_data(32768, 8))
    # pd.set_option('display.max_columns', None)
    # pd.options.mode.chained_assignment = None
    # s = Sampler(sys.argv[2])
    # retval = None

    # if sys.argv[1] == "all":
    #     retval = s.get_all_lines_and_stats(num_buckets=int(sys.argv[3]), cls=64)
    # else:
    #     type_data = json.loads(sys.argv[11].replace("\\'", '"')) if len(sys.argv) >= 12 else dict()
    #     retval = s.get_sample_of_pages(int(sys.argv[3]),                        # start_ts
    #                                    int(sys.argv[4]),                        # end_ts
    #                                    type_data,                               # type_data
    #                                    page_size=int(sys.argv[5]),
    #                                    cls=int(sys.argv[6]),
    #                                    cluster_alg=sys.argv[7],                 
    #                                    max_run_length=int(sys.argv[8]),
    #                                    max_runs_from_cluster=int(sys.argv[9]),
    #                                    num_buckets=int(sys.argv[10]))

    # print(json.dumps(retval, ignore_nan=True))
    # sys.stdout.flush()