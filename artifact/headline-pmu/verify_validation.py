"""Verify retained validation arithmetic; never run workloads or rewrite evidence."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from lib import rocksdb_timing

ARMS = ('plain', 'old', 'fixed')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected):
    check(math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-8),
          f'Retained arithmetic differs: {actual} versus {expected}')


def aio_ratios(rates):
    p, o, f = (rates[a] for a in ARMS)
    return dict(old_loss_percent=100*(1-o/p), fixed_loss_percent=100*(1-f/p),
                fixed_vs_old_percent=100*(f/o-1))


def verify_aio(data):
    rows = data['cells']
    expected = {(app, arm, b) for app in ('bcco', 'hsl') for arm in ARMS for b in (1, 2, 3)}
    check(len(rows) == 18 and {(r['application'], r['arm'], r['block']) for r in rows} == expected,
          'AIO missing/duplicate identities')
    for app in ('bcco', 'hsl'):
        selected = [r for r in rows if r['application'] == app]
        summary = data['summary'][app]
        means = {}
        for arm in ARMS:
            rates = [r['throughput'] for r in selected if r['arm'] == arm]
            check(all(math.isfinite(r) and r > 0 for r in rates), 'Invalid AIO rate')
            means[arm] = statistics.mean(rates)
            for key, value in dict(mean=means[arm], minimum=min(rates), maximum=max(rates)).items():
                close(summary['throughput'][arm][key], value)
        check([b['block'] for b in summary['blocks']] == [1, 2, 3], 'AIO block summaries')
        for b in summary['blocks']:
            rates = {r['arm']: r['throughput'] for r in selected if r['block'] == b['block']}
            for k, v in aio_ratios(rates).items(): close(b[k], v)
        for k, v in aio_ratios(means).items(): close(summary['ratio_of_means'][k], v)
    return data['summary']


def hsl_ratios(rates):
    p, o, f = (rates[a] for a in ARMS)
    return dict(old_vs_plain_pct=100*(o/p-1), fixed_vs_plain_pct=100*(f/p-1),
                fixed_vs_old_pct=100*(f/o-1))


def verify_hsl(data, inputs):
    expected = {(arm, b) for arm in ARMS for b in range(4, 10)}
    rows = data['cells']
    for values in (rows, inputs):
        check(len(values) == 18 and {(r['arm'], r['block']) for r in values} == expected,
              'HSL missing/duplicate identities')
    lookup = {(r['arm'], r['block']): r for r in inputs}
    keys = ('throughput', 'reader_only_throughput', 'native_exact_elapsed_seconds',
            'reader_only_elapsed_seconds', 'writer_completion_from_reader_start_seconds',
            'writer_tail_after_readers_seconds', 'native_post_worker_gap_seconds',
            'writer_elapsed_seconds', 'operation_count')
    for row in rows:
        parsed = rocksdb_timing.parse(lookup[row['arm'], row['block']]['text'], 96)
        for key in keys:
            close(row[key], parsed['native_throughput' if key == 'throughput' else key])
    for arm in ARMS:
        for key in keys:
            values = [r[key] for r in rows if r['arm'] == arm]
            derived = dict(mean=statistics.mean(values), sample_sd=statistics.stdev(values),
                           min=min(values), max=max(values))
            for k, v in derived.items(): close(data['groups'][arm][key][k], v)
    check([b['block'] for b in data['blocks']] == list(range(4, 10)), 'HSL block summaries')
    for key in ('throughput', 'reader_only_throughput'):
        for b in data['blocks']:
            rates = {r['arm']: r[key] for r in rows if r['block'] == b['block']}
            for k, v in hsl_ratios(rates).items(): close(b['metrics'][key][k], v)
        means = {arm: data['groups'][arm][key]['mean'] for arm in ARMS}
        for k, v in hsl_ratios(means).items(): close(data['ratios_of_means'][key][k], v)
    return data['ratios_of_means']


def verify(root=ROOT):
    root = Path(root)
    for entry in json.loads((root/'publication-manifest.json').read_text()):
        actual = hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()
        check(actual == entry['sha256'], 'Evidence hash mismatch: ' + entry['path'])
        if 'source_sha256' in entry:
            check(actual == entry['source_sha256'], 'Evidence differs from its retained source')
    for folder, db_count in (('aio-validation', 9), ('hsl-timing', 18)):
        audit = json.loads((root/folder/'audit.json').read_text())
        check(audit['status'] == 'passed' and audit['cells'] == 18 and
              audit['trace_archives'] == 12 and audit['database_archives'] == db_count,
              'Unexpected audit receipt')
    aio = verify_aio(json.loads((root/'aio-validation/numerical-summary.json').read_text()))
    hsl = verify_hsl(json.loads((root/'hsl-timing/numerical-summary.json').read_text()),
                     json.loads((root/'hsl-timing/endpoint-reports.json').read_text()))
    return dict(status='passed', aio_cells=18, hsl_cells=18, aio=aio, hsl=hsl,
                scope='Retained evidence hashes and arithmetic; no measurement or archive re-audit')


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
