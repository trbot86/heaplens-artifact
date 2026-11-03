"""Research-only equal-output temporal cache ablation; never edits production code.

The direct reference uses the production spatial helper on a NumPy time slice.
Only endpoint accumulation and the final cumulative sum are replaced. Both
implementations use identical object reconstruction, fields, and output code.
Run each worker in its own externally time/memory-limited process or container.
"""
import argparse
import contextlib
import hashlib
import inspect
import io
import json
import random
import resource
import signal
import sys
import textwrap
import time
from pathlib import Path


def load_sampler(root):
    sys.path.insert(0, str(Path(root) / 'sifter_vis_d3/server'))
    import sampler
    return sampler


def direct_method(module):
    source = textwrap.dedent(inspect.getsource(module.Sampler.get_cache_data))
    old = '''            add_cache_range(data, alloc_time_bucket, start_set, type_idx,
                            n_sets, num_cache_sets, 1)

            if free_time_bucket >= 0:
                add_cache_range(data, free_time_bucket, start_set, type_idx,
                                n_sets, num_cache_sets, -1)'''
    new = '''            end_bucket = len(data) if free_time_bucket < 0 else free_time_bucket
            if alloc_time_bucket < end_bucket:
                add_cache_range(data, slice(alloc_time_bucket, end_bucket),
                                start_set, type_idx, n_sets, num_cache_sets, 1)
            elif alloc_time_bucket > end_bucket:
                add_cache_range(data, slice(end_bucket, alloc_time_bucket),
                                start_set, type_idx, n_sets, num_cache_sets, -1)'''
    old, new = textwrap.indent(old, '    '), textwrap.indent(new, '    ')
    if source.count(old) != 1 or source.count('    df = df.cumsum()') != 1:
        raise RuntimeError('Production cache method changed; review the ablation adapter.')
    source = source.replace(old, new).replace('    df = df.cumsum()',
        '    # Direct accumulation already contains occupancy at each bucket.')
    scope = dict(vars(module))
    exec(compile(source, '<research-direct-cache-reference>', 'exec'), scope)
    return scope['get_cache_data'], source


def self_test(module):
    import numpy as np
    import pandas as pd
    from cache_ranges import add_cache_range
    rng = random.Random(20260929)
    cases = 0
    # Independently enumerate line-to-set mappings for an additional oracle.
    for _ in range(500):
        b, sets, types = rng.randrange(2, 40), rng.randrange(1, 17), rng.randrange(1, 5)
        endpoints = np.zeros((b, sets, types))
        direct = np.zeros_like(endpoints)
        oracle = np.zeros_like(endpoints)
        for _ in range(rng.randrange(1, 30)):
            a, f = rng.randrange(b), rng.choice([None, rng.randrange(b)])
            start, tp, count = rng.randrange(sets), rng.randrange(types), rng.randrange(4*sets+1)
            add_cache_range(endpoints, a, start, tp, count, sets, 1)
            if f is not None:
                add_cache_range(endpoints, f, start, tp, count, sets, -1)
            end = b if f is None else f
            if a != end:
                add_cache_range(direct, slice(min(a, end), max(a, end)),
                                start, tp, count, sets, 1 if a < end else -1)
            for bucket in range(b):
                delta = int(bucket >= a) - int(f is not None and bucket >= f)
                for line in range(count):
                    oracle[bucket, (start + line) % sets, tp] += delta
        assert np.array_equal(endpoints.cumsum(axis=0), oracle)
        assert np.array_equal(direct, oracle)
        cases += 1
    method, source = direct_method(module)
    # Exercise the complete production method, including expanded fields,
    # wrapping, unaligned objects, null/same-bucket/reversed free timestamps.
    for b in (2, 17, 2000):
        s = module.Sampler.__new__(module.Sampler)
        s.page_size, s.cache_line_size, s.num_buckets = 4096, 64, b
        s.min_ts, s.max_ts = 0, 10000
        objects = pd.DataFrame([
            ['fixture', 32, 4096, 'Node', 0, None, 1, 4096],
            ['fixture', 80, 4150, 'Node', 100, 100, 2, 4150],
            ['fixture', 9000, 8190, 'Region', 500, 9500, 3, 8190],
            ['fixture', 80, 6000, 'Node', 7000, 2000, 4, 6000],
            ['fixture', 64, 16384, 'Node', 10000, None, 5, 16384],
        ], columns=module.event_labels)
        s.all_data = objects
        s.get_objects = lambda _: objects.copy()
        s.types = lambda: ['Node', 'Region']
        s.get_fields = lambda _: {'Node': [{'subtype': 'long', 'offset': 8, 'size': 16}]}
        with contextlib.redirect_stdout(io.StringIO()):
            expected = module.Sampler.get_cache_data(s, 32768, 8)
            actual = method(s, 32768, 8)
        assert actual == expected
        cases += 1
    return {'equal_output_cases': cases, 'reference_source_sha256':
            hashlib.sha256(source.encode()).hexdigest()}


def worker(args, module):
    import numpy as np
    if args.policy == 'direct':
        module.Sampler.get_cache_data, _ = direct_method(module)
    np.random.seed(args.seed)
    random.seed(args.seed)
    phases = {}
    result = dict(policy=args.policy, database=args.database, page_size=args.page_size,
                  buckets=args.buckets, seed=args.seed, page_budget=128, record_budget=100000)
    started = time.perf_counter()

    def timed(name, fn):
        print(json.dumps({'checkpoint': name, 'policy': args.policy}), flush=True)
        begin = time.perf_counter()
        value = fn()
        phases[name] = time.perf_counter() - begin
        return value

    # Parent watchdog is authoritative for the full process. This alarm bounds
    # just cache preparation; external termination remains necessary for native
    # calls that do not promptly service Python signals.
    def cache_timeout(*_):
        raise TimeoutError('cache preparation exceeded configured time limit')

    s = timed('database', lambda: module.Sampler(args.database, args.page_size, 64, args.buckets))
    result['database_event_rows'] = len(s.all_data)
    types = s.types()
    lines = timed('statistics', s.get_all_lines_and_stats)
    pages = timed('pages', lambda: s.get_sample_of_pages(-1, -1, {t: True for t in types},
                  'mbkmeans', 5, 3, page_budget=128, record_budget=100000))
    signal.signal(signal.SIGALRM, cache_timeout)
    signal.alarm(getattr(args, 'cache_seconds', 30))
    try:
        cache = timed('cache', lambda: s.get_cache_data(32768, 8))
    finally:
        signal.alarm(0)
    payload = timed('json', lambda: json.dumps(dict(types=types, linesAndStats=lines,
                  pagesData=pages, cacheData=cache), separators=(',', ':'), sort_keys=True))
    result.update(total_seconds=time.perf_counter()-started, phases=phases,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  selected_pages=len(pages['page_num_events']),
                  selected_records=sum(len(p['events']) for p in pages['page_num_events'].values()),
                  payload_bytes=len(payload.encode()),
                  payload_sha256=hashlib.sha256(payload.encode()).hexdigest(),
                  cache_sha256=hashlib.sha256(json.dumps(cache, sort_keys=True).encode()).hexdigest(),
                  status='complete')
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', required=True)
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--policy', choices=['prefix', 'direct'], default='prefix')
    ap.add_argument('--database')
    ap.add_argument('--page-size', type=int, default=4096)
    ap.add_argument('--buckets', type=int, default=2000)
    ap.add_argument('--seed', type=int, default=20260929)
    ap.add_argument('--output')
    args = ap.parse_args()
    module = load_sampler(args.root)
    if args.self_test:
        print(json.dumps(self_test(module)))
    else:
        if not args.database or not args.output:
            ap.error('--database and --output are required for a worker')
        worker(args, module)
