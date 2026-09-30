"""Research-only spatial-by-temporal cache ablation; production files unchanged."""
import argparse
import json
from pathlib import Path
import numpy as np
import ablate_cache_prefix as temporal


def enumerated(data, bucket, start_set, type_idx, count, num_sets, delta):
    if count < 0:
        raise ValueError('negative cache-line count')
    indices = (np.arange(count) + start_set) % num_sets
    if isinstance(bucket, slice):
        # Basic slicing is a view. add.at preserves repeated-set multiplicity
        # for every time row without constructing a time-by-line index matrix.
        np.add.at(data[bucket], (slice(None), indices, type_idx), delta)
    else:
        np.add.at(data[bucket], (indices, type_idx), delta)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', required=True)
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--spatial', choices=['enumerated', 'range'], default='range')
    ap.add_argument('--policy', choices=['direct', 'prefix'], default='prefix')
    ap.add_argument('--database')
    ap.add_argument('--page-size', type=int, default=4096)
    ap.add_argument('--buckets', type=int, default=2000)
    ap.add_argument('--seed', type=int, default=20260929)
    ap.add_argument('--cache-seconds', type=int, default=150)
    ap.add_argument('--output')
    args = ap.parse_args()
    module = temporal.load_sampler(args.root)
    original = module.add_cache_range
    if args.self_test:
        rng = np.random.default_rng(20260929)
        for _ in range(1000):
            sets = int(rng.integers(1, 65))
            a = np.zeros((21, sets, 3))
            b = a.copy()
            for __ in range(10):
                start, end = sorted(rng.integers(0, 22, size=2).tolist())
                bucket = slice(start, end) if __ % 2 else int(rng.integers(21))
                params = (bucket, int(rng.integers(sets)), int(rng.integers(3)),
                          int(rng.integers(sets*5)), sets, int(rng.choice([-1,1])))
                original(a, *params)
                enumerated(b, *params)
            assert np.array_equal(a, b)
        checks = {}
        for spatial, helper in [('range', original), ('enumerated', enumerated)]:
            module.add_cache_range = helper
            checks[spatial] = temporal.self_test(module)
        print(json.dumps(dict(spatial_equal_output_cases=1000, temporal_checks=checks)))
        return
    if args.spatial == 'enumerated':
        module.add_cache_range = enumerated
    temporal.worker(args, module)
    output = Path(args.output)
    row = json.loads(output.read_text())
    row['spatial'] = args.spatial
    output.write_text(json.dumps(row, indent=2)+'\n')


if __name__ == '__main__':
    main()
