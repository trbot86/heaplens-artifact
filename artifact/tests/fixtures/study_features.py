"""Unmodified executed study feature builder (2026-10-09), for equivalence tests."""
import json
import numpy as np
from scipy import sparse
def save(path, data):
    path.write_text(json.dumps(data))

def numeric_features(df, times):
    if df.empty:
        return {}, []
    columns = np.array([t+' '+str(int(a)%128) for t,a in zip(df.type,df.addr)])
    names, ids = np.unique(columns, return_inverse=True)
    counts = np.bincount(ids, minlength=len(names))
    history = dict(zip(names, map(int, counts)))
    alloc = df.allocTs.to_numpy(dtype=np.int64)
    free = df.freeTs.fillna(np.iinfo(np.int64).max).to_numpy(dtype=np.int64)
    seen = {}
    snapshots = []
    for i, ts in enumerate(times):
        live = (alloc <= ts)&(free > ts)
        if not live.any():
            continue
        values = np.bincount(ids[live], minlength=len(names))
        key = values.tobytes()
        if key not in seen:
            seen[key] = len(snapshots)
            snapshots.append(dict(first=i, times=[], counts={n:int(v) for n,v in zip(names,values) if v}))
        snapshots[seen[key]]['times'].append(i)
    return history, snapshots

class MatrixBuilder:
    def __init__(self):
        self.columns = {}
        self.indices = []
        self.values = []
        self.pointers = [0]
        self.pages = []
        self.first = []

    def append(self, page, first, counts):
        self.pages.append(page)
        self.first.append(first)
        for name, value in counts.items():
            if name not in self.columns:
                self.columns[name] = len(self.columns)
            self.indices.append(self.columns[name])
            self.values.append(value)
        self.pointers.append(len(self.values))

    def finish(self, folder, prefix):
        names = sorted(self.columns)
        permutation = [self.columns[n] for n in names]
        mat = sparse.csr_matrix((np.asarray(self.values,dtype=np.int64),
                                np.asarray(self.indices,dtype=np.int32),
                                np.asarray(self.pointers,dtype=np.int64)),
                               shape=(len(self.pages),len(names)))[:,permutation]
        order = np.lexsort((self.pages,self.first))
        mat = mat[order]
        sparse.save_npz(folder/(prefix+'.npz'), mat)
        np.savez(folder/(prefix+'-index.npz'), pages=np.asarray(self.pages,dtype=np.int64)[order],
                 first=np.asarray(self.first,dtype=np.int16)[order])
        save(folder/(prefix+'-columns.json'), names)
