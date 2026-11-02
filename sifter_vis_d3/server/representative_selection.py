"""Ordinary-backend adapter for the final paper's frozen selection algorithm."""
import hashlib
import random

import numpy as np
import pandas as pd

from cluster_priority import ClusterGeometry
from page_selection import DEFAULT_PAGE_BUDGET, DEFAULT_RECORD_BUDGET, select_pages
from temporal_fingerprints import (regular_times, quantize, compress_observations,
                                   cluster_features, cluster_pages)

MODES = ('full', 'no_per_time', 'no_coverage_first', 'no_alternation')


def derived_seed(seed, stream):
    return int.from_bytes(hashlib.sha256(f'{seed}/{stream}'.encode()).digest()[:4], 'little')


def fingerprint_inputs(objects, start, end, page_size, cache_line_size=64):
    """Preserve the study's first-time, then page observation row order.

    Fingerprints use unreduced lifetimes. Repeated raw observations are collapsed
    before quantization, then equal quantized vectors on a page are collapsed.
    Row ordering matters for deterministic minibatch k-means replay.
    """
    history, pages, snapshots, metadata = [], [], [], []
    times = regular_times(start, end, 16)
    for page, rows in objects.groupby(objects.addr // page_size, sort=True):
        columns = np.array([t + ' ' + str(int(a) % (2 * cache_line_size))
                            for t, a in zip(rows.type, rows.addr)])
        names, ids = np.unique(columns, return_inverse=True)
        history.append(dict(zip(names, map(int, np.bincount(ids, minlength=len(names))))))
        pages.append(int(page))
        alloc = rows.allocTs.to_numpy(dtype=np.int64)
        # Production lifetimes may use float NaNs; filling with int64.max in a
        # float column rounds to 2**63 and wraps negative on conversion.
        free = np.full(len(rows), np.iinfo(np.int64).max, dtype=np.int64)
        known = rows.freeTs.notna().to_numpy()
        free[known] = rows.freeTs[known].to_numpy(dtype=np.int64)
        seen = set()
        for ts in times:
            live = (alloc <= ts) & (free > ts)
            if not live.any():
                continue
            values = np.bincount(ids[live], minlength=len(names))
            key = values.tobytes()
            if key in seen:
                continue
            seen.add(key)
            snapshots.append({n: int(v) for n, v in zip(names, values) if v})
            metadata.append(dict(page=int(page), timestamp=ts, source='regular'))
    hist = pd.DataFrame(history, index=pages).fillna(0).sort_index(axis=1)
    hist.index.name = 'page_num'
    order = sorted(range(len(metadata)), key=lambda i: (metadata[i]['timestamp'], metadata[i]['page']))
    raw = pd.DataFrame([snapshots[i] for i in order]).fillna(0).sort_index(axis=1)
    metadata = [metadata[i] for i in order]
    return quantize(hist), compress_observations(raw, metadata)


def prepare_selection(objects, reduced, start, end, page_size, cache_line_size=64,
                      page_budget=DEFAULT_PAGE_BUDGET, record_budget=DEFAULT_RECORD_BUDGET,
                      seed=0, mode='full', forced_pages=(), coverage_types=None,
                      max_run_length=5, max_runs_per_cluster=3):
    if mode not in MODES:
        raise ValueError('Unknown selection mode')
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise ValueError('Selection seed must be a nonnegative 32-bit integer')
    groups = reduced.groupby(reduced.addr // page_size, sort=True)
    costs = {int(p): int(len(rows)) for p, rows in groups}
    types = {int(p): set(rows.type) for p, rows in groups}
    # A page without any display records cannot consume a selection slot.
    objects = objects[(objects.addr // page_size).isin(costs)]
    hist, observations = fingerprint_inputs(objects, start, end, page_size, cache_line_size)
    ntypes = len(set().union(*types.values()))
    cluster_seed, selection_seed = derived_seed(seed, 'clustering'), derived_seed(seed, 'selection')
    hl, hc = cluster_features(hist, ntypes, random_state=cluster_seed, return_centers=True)
    histories = cluster_pages(hl, hist.index)
    tl, tc = cluster_features(observations.features, ntypes, random_state=cluster_seed, return_centers=True)
    temporal = cluster_pages(tl, [m['page'] for m in observations.metadata], 2 * ntypes)
    use_temporal = mode != 'no_per_time'
    clusters = {**histories, **temporal} if use_temporal else histories
    centers = {**hc, **{c + 2 * ntypes: v for c, v in tc.items()}} if use_temporal else hc
    geometry = ClusterGeometry(centers, {c: int(c >= 2 * ntypes) for c in clusters})
    selected, details = select_pages(clusters, types, page_budget,
        max_run_length, max_runs_per_cluster, forced_pages=forced_pages,
        coverage_types=coverage_types, rng=random.Random(selection_seed),
        page_records=costs, record_budget=record_budget, overlapping_clusters=True,
        cluster_priority='shuffled' if mode == 'no_alternation' else 'balanced50',
        cluster_geometry=geometry, cluster_coverage_first=mode != 'no_coverage_first')
    primary = {int(p): int(c) for p, c in zip(hist.index, hl)}
    memberships = {p: [int(c) for c, members in clusters.items() if p in members] for p in sorted(selected)}
    details.update(mode=mode, seed=seed, cluster_seed=cluster_seed, selection_seed=selection_seed,
                   fingerprint_times=16, history_clusters=len(histories),
                   per_time_clusters=len(temporal) if use_temporal else 0,
                   eligible_pages=len(costs))
    return selected, details, clusters, primary, memberships, hist


def sample_pages(sampler, start_ts, end_ts, type_data, event_labels,
                 page_budget=DEFAULT_PAGE_BUDGET, record_budget=DEFAULT_RECORD_BUDGET,
                 seed=0, mode='full', max_run_length=5, max_runs_per_cluster=3):
    objects = sampler.get_objects(sampler.all_data.copy())
    perf = sampler.get_perf_data()
    forced = set((perf.cl_addr // sampler.page_size).tolist())
    if start_ts >= 0:
        objects = objects[objects.freeTs.isna() | (objects.freeTs >= start_ts)]
    eligible = objects.type.map(lambda t: type_data.get(t, True)) | (objects.addr // sampler.page_size).isin(forced)
    keep = set((objects.loc[eligible, 'addr'] // sampler.page_size).tolist())
    objects = objects[(objects.addr // sampler.page_size).isin(keep)].copy()
    reduced = sampler.get_last_object_per_bucket(objects.copy()) if len(objects) else objects.copy()
    start = sampler.min_ts if start_ts < 0 else start_ts
    end = sampler.max_ts if end_ts < 0 else end_ts
    selected, details, clusters, primary, memberships, hist = prepare_selection(
        objects, reduced, start, end, sampler.page_size, sampler.cache_line_size,
        page_budget, record_budget, seed, mode, forced,
        {t for t in reduced.type if type_data.get(t, True)}, max_run_length, max_runs_per_cluster)
    page_data = {}
    for page, rows in reduced.groupby(reduced.addr // sampler.page_size, sort=True):
        page = int(page)
        if page not in selected:
            continue
        events = rows[event_labels].astype(object).where(pd.notna(rows[event_labels]), None).to_dict('records')
        page_data[str(page * sampler.page_size)] = dict(events=events, cluster=primary[page], clusters=memberships[page])
    return dict(page_num_events=page_data,
        clusters={int(c): dict(pages=sorted(set(ps) & selected), size=len(ps)) for c, ps in clusters.items()},
        sum_cluster_sizes=details['eligible_pages'], num_clusters=len(clusters), selection=details,
        clusterMemberships=memberships,
        features={int(p): {str(t): int(v) for t, v in hist.loc[p].items() if v > 0} for p in sorted(selected)})
