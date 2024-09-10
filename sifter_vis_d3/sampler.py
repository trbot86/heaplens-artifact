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
import simplejson as json
import math
import os
from random import randint, shuffle

MAX_PAGE_PROP = 7560
MAX_OBJ_STATS = 1000000
CHANGE_POINT_THRESHOLD = 10
event_labels = ['file', 'size', 'addr', 'type', 'allocTs', 'freeTs']

def replace_nan(event, key):
    if math.isnan(event[key]):
        event[key] = None
    return event


class Sampler:

    def __init__(self, dbfile):
        self.con = sqlite3.connect(dbfile)

    def __del__(self):
        self.con.close()

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
        return df.loc[df["is_alloc"] == 1,:].drop(columns=["is_alloc"]).dropna(subset=["allocTs"])
    
    def get_all_records(self, page_size=4096):
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
    
    def get_counts(self):
        try:
            df = pd.read_sql_query("""SELECT TYPE as type,
                                        ALLOCS as numAllocs,
                                        PAGES as numPages
                                    FROM STATS""",
                                    self.con)
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
        
    def get_last_object_per_bucket(self, df, num_buckets):
        min_ts = df[['allocTs', 'freeTs']].min().min()
        max_ts = df[['allocTs', 'freeTs']].max().max()
        bucket_size = (max_ts - min_ts) / num_buckets
        df.loc[:,'bucket'] = ((df['allocTs'] - min_ts) // bucket_size).astype('Int64')

        last_allocs = df.groupby(['addr', 'type', 'bucket']).agg({'allocTs': 'last'})
        last_allocs = last_allocs.merge(df, how='left', on=['addr', 'type', 'allocTs'])
        return last_allocs
    
    def get_all_lines_and_stats(self, num_buckets=1000, cls=64):
        recs = self.get_all_records()
        df = self.add_free_types(recs).dropna(subset=['file','size','type'])
        min_ts = df['ts'].min()
        max_ts = df['ts'].max()
        bucket_size = (max_ts - min_ts) / num_buckets
        df.loc[:,'bucket'] = ((df['ts'] - min_ts) // bucket_size).astype('Int64')

        # print(df)
        pts = {}
        change_pts = {}
        for tp in df.loc[:, 'type'].unique():
            type_df_alloc = df[(df['type'] == tp) & (df['is_alloc'] == 1)][['ts', 'addr', 'size', 'bucket']]
            type_df_free = df[(df['type'] == tp) & (df['is_alloc'] == 0)][['ts', 'addr', 'size', 'bucket']]
            type_df_free['size'] = type_df_free['size'] * -1
            # type_df_alloc.rename(columns={'allocTs': 'ts'}, inplace=True)
            # type_df_free.rename(columns={'freeTs': 'ts'}, inplace=True)
            merged = type_df_alloc.merge(type_df_free, how='outer', sort=True)
            sum_allocs = merged.groupby(['addr', 'bucket']).agg({'size': 'sum', 'ts': 'last'}).sort_values('ts')

            df_pts = sum_allocs.set_index('ts').cumsum()
            pts[tp] = [{'ts': int(rec[0]), 'size': int(rec[1])} for rec in zip(df_pts.index.to_list(), df_pts['size'])]
            # if len(df[df['type'] == tp]) >= CHANGE_POINT_THRESHOLD:
            #     change_point_alg = rpt.Window(width=150, model='l2', min_size=CHANGE_POINT_THRESHOLD).fit(df_pts)
            #     change_pts[tp] = list(map(int, change_point_alg.predict(pen=20)))

        objects = self.get_objects(recs) if len(recs.index) < 2000000 else self.get_last_object_per_bucket(self.get_objects(recs), num_buckets).drop(columns=['bucket'])

        # print(f"cols in objects: {self.get_objects(recs).columns}")
        # print(f"cols in objects: {objects.columns}")

        return {'recs': objects.drop(columns=['file']).to_dict('records'), 'pts': pts, 'changes': change_pts,
                'stats': {'single': self.get_stats(recs, cls), 'double': self.get_stats(recs, 2*cls)},
                'fields': self.get_fields(s.replace(' ', '') for s in df['type'].unique()),
                'counts': self.get_counts().set_index('type').to_dict('index')}
        # 'records': df.to_dict(orient='records'), 

    def get_records_in_interval(self, start_ts, end_ts, page_size=4096):
        df = pd.read_sql_query("""SELECT FILE as file,
                                    SIZE as size,
                                    ADDRESS as addr,
                                    TYPE as type,
                                    TIMESTAMP as ts,
                                    isNew as is_alloc
                                FROM SUPERTABLE
                                WHERE is_alloc=0 OR (ts <= {} AND is_alloc=1)""".format(end_ts),
                                self.con)
                                # dtype={'file': object,
                                #        'size': int,
                                #        'addr': int,
                                #        'type': object,
                                #        'ts': int,
                                #        'is_alloc': int})
        return df
        # TODO: change this to get alloc events before start if matching free is after start
        # TODO: just send the objects themselves, not individual allocs & frees
        # TODO: sort into page nums as well
    
    def get_perf_data(self):
        try:
            df = pd.read_sql_query("""SELECT CLADDRESS as cl_addr,
                                        HITM as hitm
                                    FROM PERF""",
                                    self.con)
            return df
        except:
            return pd.DataFrame({"cl_addr": [], "hitm": []})

    def get_fields(self, types):
        try:
            df = pd.read_sql_query("""SELECT TYPE as type,
                                        SUBTYPE as subtype,
                                        NAME as name,
                                        SIZE as size,
                                        OFFSET as offset
                                    FROM FIELDS""",
                                    self.con)
            return {k: v.to_dict(orient='records') for k, v in df[df['type'].isin(types)].set_index('type').groupby(level=0)}
        except:
            return dict()

    def get_clusters_of_pages(self, start_ts, end_ts, type_data, page_size=4096, alg='dbscan', cls=64, num_buckets=1000):
        recs = self.get_records_in_interval(start_ts, end_ts, page_size) if start_ts > 0 and end_ts > 0 else self.get_all_records()
        # df = self.__add_free_types(recs).dropna(subset=['size'])
        df = self.get_objects(recs)
        df = df.drop(df[df['freeTs'] < start_ts].index)
        df.loc[:,'page_num'] = df.loc[:,'addr'] // page_size

        perf_df = self.get_perf_data()
        #TODO: should the following be multiplied by cls? Or is this just raw virt address?
        perf_df.loc[:,'page_num'] = perf_df.loc[:,'cl_addr'] // page_size

        # print("Here is perf df:")
        # print(perf_df)

        filter_types = pd.DataFrame({'type': list(type_data.keys()), 'mask': list(type_data.values())})
        type_entries = df.merge(filter_types, how='left', on='type')
        type_entries.loc[:,'mask'] = type_entries.loc[:,'mask'].astype(object)
        type_entries.loc[type_entries['page_num'].isin(perf_df['page_num']),'mask'] = True
        type_entries.loc[:,'mask'] = type_entries.loc[:,'mask'].fillna(True).astype(bool)
        pages_to_keep = type_entries[type_entries['mask']]['page_num']
        df = df[df['page_num'].isin(pages_to_keep)]

        # print("Here are pages to keep:")
        # print(pages_to_keep)

        last_allocs = self.get_last_object_per_bucket(df, num_buckets)

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
        df.loc[:,'align'] = df.loc[:,'addr'] % (2*cls)
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

        #TODO Take a look at FeatureAgglomeration?
        page_pattern = StandardScaler().fit_transform(merged)
        clusters = None
        if (len(merged.index) <= 1):
            clusters = [0]
        elif (alg == 'dbscan'):
            clusters = DBSCAN(eps=0.9, min_samples=1).fit_predict(page_pattern)
        elif (alg == 'agglomerative'):
            clusters = AgglomerativeClustering(n_clusters=None, distance_threshold=10).fit_predict(page_pattern)
        elif (alg == 'meanshift'):
            clusters = MeanShift(min_bin_freq=1, cluster_all=False).fit_predict(page_pattern)
        merged['cluster'] = clusters
        
        pages = pd.DataFrame.from_dict({page: [group[event_labels].values.tolist()]
                    for page, group in last_allocs.groupby('page_num')}, orient='index')
        pages.index.name = 'page_num'
        labeled = pages.merge(merged.loc[:,'cluster'], on='page_num')
        # labeled = pages
        # merged['cluster'] = 0
        # labeled['cluster'] = 0

        return labeled, merged, perf_df

    def get_sample_of_pages(self, start_ts, end_ts, type_data, page_size=4096, cls=64, cluster_alg='dbscan', 
                            max_run_length=3, max_runs_from_cluster=2, num_buckets=1000, include_all_noise=True):
        labeled_data, features, perf_df = self.get_clusters_of_pages(start_ts, end_ts, type_data, page_size, alg=cluster_alg, cls=cls, num_buckets=num_buckets)
        # .reset_index().set_index('cluster')
        clusters = labeled_data.groupby('cluster', sort=False).groups

        max_pages = math.floor(MAX_PAGE_PROP / pow(math.log(page_size, 2), 2))
        # max_pages = 1 # DEBUGGING
        sampled_pages = set(perf_df[perf_df['page_num'].isin(labeled_data.index)]['page_num'].tolist())
        # sampled_pages.add(34165069575)
        
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
        # print(sampled_pages)
        
        sampled_pages_df = pd.DataFrame({'page_num': sorted(sampled_pages)})
        features = sampled_pages_df.merge(features, how='left', on='page_num')
        merged = sampled_pages_df.merge(labeled_data, how='left', on='page_num')
        
        dict_merged = merged.set_index('page_num').set_axis(['events', 'cluster'], axis='columns').to_dict(orient='index')
        fts = event_labels.index("freeTs")
        return {'page_num_events': {pn: {'events': [dict(zip(event_labels, replace_nan(event, fts))) for event in v['events']], 'cluster': v['cluster']} for pn, v in dict_merged.items()},
                'clusters': features.reset_index().loc[:,['cluster','page_num']].groupby('cluster').agg(lambda x: x.tolist()).to_dict(orient='index'),
                'features': {pn: {tp: int(val) for tp, val in v.items() if val > 0} for pn, v in features.set_index('page_num').drop(columns=['cluster']).to_dict(orient='index').items()},
                'perf': perf_df.set_index('cl_addr').to_dict(orient='index')}


if __name__ == "__main__":
    # pd.set_option('display.max_columns', None)
    pd.options.mode.chained_assignment = None
    s = Sampler(sys.argv[2])
    retval = None

    if sys.argv[1] == "all":
        retval = s.get_all_lines_and_stats(num_buckets=int(sys.argv[3]), cls=64)
    else:
        type_data = json.loads(sys.argv[11].replace("\\'", '"')) if len(sys.argv) >= 12 else dict()
        retval = s.get_sample_of_pages(int(sys.argv[3]),                        # start_ts
                                       int(sys.argv[4]),                        # end_ts
                                       type_data,                               # type_data
                                       page_size=int(sys.argv[5]),
                                       cls=int(sys.argv[6]),
                                       cluster_alg=sys.argv[7],                 
                                       max_run_length=int(sys.argv[8]),
                                       max_runs_from_cluster=int(sys.argv[9]),
                                       num_buckets=int(sys.argv[10]))

    print(json.dumps(retval, ignore_nan=True))
    sys.stdout.flush()