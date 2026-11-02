#!/usr/bin/env python3
"""Replay representative selection on an existing SQLite trace, without a GUI."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'sifter_vis_d3/server'))
from sampler import Sampler
from representative_selection import MODES


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('database', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--mode', choices=MODES, default='full')
    p.add_argument('--page-size', type=int, default=4096)
    p.add_argument('--cache-line-size', type=int, default=64)
    p.add_argument('--buckets', type=int, default=2000)
    p.add_argument('--page-budget', type=int, default=128)
    p.add_argument('--record-budget', type=int, default=1000000)
    args = p.parse_args()
    if not args.database.is_file():
        p.error('database must be an existing file')
    if any(getattr(args, n) < 1 for n in ('page_size','cache_line_size','buckets','page_budget','record_budget')):
        p.error('sizes and budgets must be positive')
    if not 0 <= args.seed < 2**32:
        p.error('seed must be a nonnegative 32-bit integer')
    if args.out.exists() or args.out.resolve() == args.database.resolve():
        p.error('output must be a new file')
    sampler = Sampler(str(args.database), args.page_size, args.cache_line_size, args.buckets)
    result = sampler.get_sample_of_pages(-1, -1, {}, seed=args.seed, selection_mode=args.mode,
                                        page_budget=args.page_budget, record_budget=args.record_budget)
    result['configuration'] = dict(page_size=args.page_size, cache_line_size=args.cache_line_size,
                                  buckets=args.buckets, start=sampler.min_ts, end=sampler.max_ts)
    with args.out.open('x') as f:
        json.dump(result, f, allow_nan=False)
        f.write('\n')


if __name__ == '__main__':
    main()
