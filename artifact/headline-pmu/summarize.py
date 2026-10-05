"""Recompute retained comparisons. Never launches workloads or deletes data."""
import collections
import json
import math
from pathlib import Path
import statistics


def summarize(path):
    data = json.loads(Path(path).read_text())
    apps = {'ascylib_dvy', 'ascylib_efrb', 'ascylib_hj', 'tpcc_bcco',
            'tpcc_efrb', 'rocks_isl', 'rocks_hsl', 'hnsw128', 'hnsw1536', 'valkey'}
    rows = data['rows']
    identities = [(r['application'], r['variant'], r['arm'], r['rep']) for r in rows]
    expected = {(a, v, arm, rep) for a in apps for v in ('before', 'after')
                for arm in ('plain', 'logging') for rep in range(1, 11)}
    if len(identities) != 400 or set(identities) != expected:
        raise ValueError('Missing, duplicate, or unexpected measurement identities')
    groups = collections.defaultdict(list)
    for row in rows:
        if not math.isfinite(row['throughput']) or row['throughput'] <= 0 or row['operations'] <= 0:
            raise ValueError('Invalid throughput or denominator')
        for counter in ('cycles', 'instructions', 'cache-misses', 'dTLB-load-misses'):
            if row[counter+'_coverage'] != 100:
                raise ValueError('Unexpected PMU coverage')
        groups[row['application'], row['variant'], row['arm']].append(row['throughput'])
    retained = {(r['application'], r['variant']): r for r in data['comparisons']}
    output = []
    for app in sorted(apps):
        for variant in ('before', 'after'):
            plain = statistics.mean(groups[app, variant, 'plain'])
            logging = statistics.mean(groups[app, variant, 'logging'])
            loss = 100 * (1 - logging / plain)
            if not math.isclose(loss, retained[app, variant]['throughput_loss_pct'], abs_tol=1e-9):
                raise ValueError('Retained summary differs from per-cell rows')
            output.append((app, variant, plain, logging, loss))
    return output


if __name__ == '__main__':
    print('application\tvariant\tplain_ops_s\tlogging_ops_s\tthroughput_loss_pct')
    for row in summarize(Path(__file__).with_name('campaign-numerical-summary.json')):
        print('\t'.join(str(x) for x in row))
