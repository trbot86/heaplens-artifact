"""Multi-observation fingerprints, with explicit observation times.

Inputs are reconstructed unreduced lifetimes.
Whole-history and instantaneous families are intentionally clustered separately.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import StandardScaler

def snapshot_objects(objects, snapshots, page_size):
    """Materialize explicit per-page times; no maximum-fill policy is enabled."""
    if snapshots.page_num.duplicated().any():
        raise ValueError('Expected one snapshot timestamp per page')
    rows=objects.assign(page_num=objects.addr//page_size).merge(
        snapshots,on='page_num',how='inner',validate='many_to_one')
    return rows[(rows.allocTs<=rows.snapshot_ts)&(
        rows.freeTs.isna()|(rows.freeTs>rows.snapshot_ts))].copy()



def regular_times(start, end, count=16):
    if count < 2 or end < start:
        raise ValueError('Need at least two times and a nonnegative interval')
    return sorted({int(start)+(int(end)-int(start))*i//(count-1) for i in range(count)})


def histogram(rows, page_size=4096, cache_line_size=64):
    if rows.empty:
        return pd.DataFrame()
    rows=rows.assign(page_num=rows.addr//page_size, align=rows.addr%(2*cache_line_size))
    result=rows.groupby(['page_num','type','align']).size().unstack(['type','align'],fill_value=0)
    result.columns=[' '.join(map(str,col)).strip() for col in result.columns]
    return result.sort_index(axis=1)


def quantize(counts):
    if counts.empty:
        return counts.copy()
    maximum=counts.max(axis=0).replace(0,1)
    scaled=counts.div(maximum)*3
    return np.floor(scaled.mask((scaled>0)&(scaled<1),other=1)).astype(np.int8)


@dataclass
class Observations:
    features: pd.DataFrame
    # One item per row of features. Times are (timestamp, source) pairs.
    metadata: list
    raw_observations: int


def snapshot_counts(objects, times=(), max_fill=None, page_size=4096, cache_line_size=64):
    """Return raw count rows and metadata; process one time at a time."""
    frames=[]
    metadata=[]
    for timestamp in times:
        live=objects[(objects.allocTs<=timestamp)&(objects.freeTs.isna()|(objects.freeTs>timestamp))]
        frame=histogram(live,page_size,cache_line_size)
        frames.append(frame)
        metadata.extend({'page':int(p),'timestamp':int(timestamp),'source':'regular'} for p in frame.index)
    if max_fill is not None:
        live=snapshot_objects(objects,max_fill,page_size)
        frame=histogram(live,page_size,cache_line_size)
        frames.append(frame)
        lookup=max_fill.set_index('page_num').snapshot_ts
        metadata.extend({'page':int(p),'timestamp':int(lookup.loc[p]),'source':'max_fill'} for p in frame.index)
    counts=pd.concat(frames,ignore_index=True).fillna(0).sort_index(axis=1) if frames else pd.DataFrame()
    assert len(counts)==len(metadata)
    return counts,metadata


def compress_observations(counts, metadata):
    if len(counts) != len(metadata):
        raise ValueError('Expected one metadata entry per fingerprint')
    features=quantize(counts)
    vectors=features.to_numpy(dtype=np.int8)
    seen={}
    keep=[]
    compressed=[]
    for i,(vector,entry) in enumerate(zip(vectors,metadata)):
        key=(entry['page'],vector.tobytes())
        if key not in seen:
            seen[key]=len(compressed)
            keep.append(i)
            compressed.append({'page':entry['page'],'times':[]})
        observation=compressed[seen[key]]
        stamp=(entry['timestamp'],entry['source'])
        if stamp not in observation['times']:
            observation['times'].append(stamp)
    return Observations(features.iloc[keep].reset_index(drop=True),compressed,len(metadata))


def cluster_features(features, num_types, random_state=None, return_centers=False):
    if features.empty:
        labels = np.array([],dtype=np.int64)
        return (labels, {}) if return_centers else labels
    if len(features)==1:
        labels = np.zeros(1,dtype=np.int64)
        return (labels, {0: np.zeros(features.shape[1])}) if return_centers else labels
    # Match the existing pivot-table's column-major matrix. StandardScaler's
    # floating-point reductions depend on layout; tiny differences can alter
    # k-means ties among repeated vectors even when feature values are identical.
    values=np.asfortranarray(features.to_numpy(),dtype=np.float64)
    scaled=StandardScaler().fit_transform(values)
    # Preserve installed sklearn's existing default n_init for the old arm.
    model=MiniBatchKMeans(n_clusters=min(2*num_types,len(features)),random_state=random_state)
    labels=model.fit_predict(scaled)
    if return_centers:
        return labels, {int(c): model.cluster_centers_[c].copy() for c in np.unique(labels)}
    return labels


def cluster_pages(labels, pages, offset=0):
    if len(labels) != len(pages):
        raise ValueError('Expected one cluster label per observation')
    clusters={}
    for label,page in zip(labels,pages):
        clusters.setdefault(int(label)+offset,set()).add(int(page))
    return {cluster:sorted(members) for cluster,members in clusters.items()}
