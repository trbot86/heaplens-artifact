#!/usr/bin/env python3
"""Table 1 performance entry point using the frozen, phase-gated drivers."""
import argparse
from pathlib import Path
import sys
import time

BUNDLE = Path(__file__).resolve().parent / 'headline-pmu/reproduction'
sys.path.insert(0, str(BUNDLE))
import launch
from protocol import APPLICATIONS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'reproduce'])
    parser.add_argument('--apps', nargs='+', choices=APPLICATIONS, required=True)
    parser.add_argument('--reps', type=int, choices=range(1, 11), default=10)
    parser.add_argument('--out', type=Path, help='Fresh absolute Linux directory outside the artifact for work and archives')
    parser.add_argument('--data-root', type=Path, help='Fresh absolute Linux directory for live results and RocksDB databases')
    parser.add_argument('--image', default='heaplens-atc26:submission')
    parser.add_argument('--server-node', type=int, default=0)
    parser.add_argument('--client-node', type=int, default=1)
    parser.add_argument('--lock-file', type=Path, default=Path('/tmp/heaplens-headline-pmu.lock'))
    parser.add_argument('--timeout-hours', type=float, default=72)
    parser.add_argument('--acknowledge-cost', action='store_true')
    args = parser.parse_args(argv)
    selection = ['--apps', *args.apps, '--reps', str(args.reps), '--arms', 'plain']
    if args.action == 'plan':
        launch.main(['plan', *selection])
        return
    if not args.acknowledge_cost:
        parser.error('reproduce requires --acknowledge-cost; plan launches nothing')
    if args.out is None or args.data_root is None:
        parser.error('Specify --out and --data-root; preserve existing attempts')
    if not 0 < args.timeout_hours <= 168:
        parser.error('Choose a positive bound of at most 168 hours')
    if args.out.exists() or args.data_root.exists():
        parser.error('Fresh paths required; no automatic retry or resume')
    options = [*selection, '--work-root', str(args.out / 'work'),
               '--archive-root', str(args.out / 'archives'), '--data-root', str(args.data_root),
               '--image', args.image, '--server-node', str(args.server_node),
               '--client-node', str(args.client_node), '--lock-file', str(args.lock_file),
               '--acknowledge-cost']
    deadline = time.monotonic() + args.timeout_hours * 3600
    for action in ('preflight', 'build', 'run'):
        remaining = (deadline - time.monotonic()) / 3600
        if remaining <= 0:
            raise TimeoutError('Table 1 overall bound reached; attempt preserved')
        launch.main([action, *options, '--timeout-hours', str(remaining)])


if __name__ == '__main__':
    main()
