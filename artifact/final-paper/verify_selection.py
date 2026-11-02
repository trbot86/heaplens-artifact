#!/usr/bin/env python3
"""Recompute the saved selection aggregates from individual audited trials."""
import gzip
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def verify(trials, summary):
    protocol = summary['protocol']
    expected = {(app, float(p), float(s), seed)
                for app in protocol['inputs'] for p, s in protocol['sampling']
                for seed in protocol['seeds']}
    observed = [(t['application'], float(t['p']), float(t['s']), t['seed'])
                for t in trials['trials']]
    if len(observed) != len(set(observed)) or set(observed) != expected:
        raise ValueError('Missing, duplicate, or unexpected trial identity')
    arms = {f'{b}:{a}' for b in protocol['page_budgets'] for a in protocol['arms']}
    for trial in trials['trials']:
        if set(trial['results']) != arms:
            raise ValueError('Incomplete method/budget set')
        for result in trial['results'].values():
            if len(result['pages']) != len(set(result['pages'])):
                raise ValueError('Repeated selected page')
            for quality in result['quality'].values():
                if not quality['same_page_unreduced_truth_guard'] or quality['selected_duration_ticks'] < 0:
                    raise ValueError('Invalid same-page truth guard or duration')
    for cell in summary['cells']:
        samples = [t for t in trials['trials'] if t['application'] == cell['application']
                   and [t['p'], t['s']] == cell['sampling']]
        qualities = [t['results'][f"{cell['page_budget']}:{cell['arm']}"]['quality'][cell['pattern']]
                     for t in samples]
        reference = trials['references'][cell['application']]['durations'][cell['pattern']]
        coverage = statistics.mean(q['selected_duration_ticks'] / reference for q in qualities) if reference else None
        if (len(qualities) != cell['completed'] or len(qualities) != cell['expected']
                or sum(q['any_time_survival'] for q in qualities) != cell['any_time']
                or sum(q['grid_survival'] for q in qualities) != cell['grid']
                or reference != cell['reference_duration_ticks']
                or (reference == 0) != cell['pattern_absent']):
            raise ValueError(f"Count/reference mismatch: {cell['application']}/{cell['pattern']}")
        saved = cell['duration_coverage_mean']
        if (coverage is None) != (saved is None) or (coverage is not None and
                not math.isclose(coverage, saved, rel_tol=0, abs_tol=1e-12)):
            raise ValueError(f"Coverage mismatch: {cell['application']}/{cell['pattern']}")
    return dict(trials=len(observed), method_budget_outputs=len(observed)*len(arms),
                aggregate_cells=len(summary['cells']), all_aggregates_match=True)


def main():
    with gzip.open(HERE/'selection-trials.json.gz', 'rt', encoding='utf-8') as stream:
        trials = json.load(stream)
    summary = json.loads((HERE/'selection-summary.json').read_text(encoding='utf-8'))
    print(json.dumps(verify(trials, summary), indent=2))


if __name__ == '__main__':
    main()
