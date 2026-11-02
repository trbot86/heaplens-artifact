"""Keep compact derived results on the branch; leave large traces outside git."""
import argparse
import json
from pathlib import Path
from statistics import median

ap = argparse.ArgumentParser()
ap.add_argument('workspace', type=Path)
ap.add_argument('--out', type=Path, required=True)
a = ap.parse_args()
selection_root = a.workspace / 'artifact-tools/cluster-first-20260928'
profile_root = a.workspace / 'artifact-tools/camera-ready-profiles-20260928'
selection = []
for path in sorted(selection_root.glob('*/results.json')):
    result = json.loads(path.read_text())
    rows = []
    for policy in ('baseline', 'cluster-first'):
        for budget in sorted({r['budget'] for r in result['trials']}):
            group = [r for r in result['trials'] if r['policy'] == policy and r['budget'] == budget]
            def bounds(field):
                return [min(r[field] for r in group), max(r[field] for r in group)]
            row = dict(policy=policy, budget=budget, trials=len(group),
                       all_clusters=sum(r['represented_clusters'] == r['available_clusters'] for r in group),
                       all_types=sum(r['represented_types'] == r['available_types'] for r in group),
                       available_clusters=bounds('available_clusters'),
                       represented_clusters=bounds('represented_clusters'),
                       available_types=bounds('available_types'),
                       represented_types=bounds('represented_types'),
                       selected_pages=bounds('selected_pages'),
                       over_budget=sum(r['selected_pages'] > budget for r in group),
                       selection_median_ms=1000 * median(r['selection_seconds'] for r in group))
            if 'rax_success' in group[0]:
                row['rax_success_trials'] = sum(r['rax_success'] for r in group)
                row['rax_genuine_objects'] = bounds('rax_genuine_objects')
            rows.append(row)
    selection.append({**{k: v for k, v in result.items() if k != 'trials'}, 'summary': rows})

ui = json.loads((profile_root / 'ui-computation-same-realm.json').read_text())
for row in ui['rows']:
    # Derive the ordinary even-sample median from raw observations. The first
    # saved pilot JSON used the upper middle observation instead.
    row['old_median_ms'] = median(row['old_ms'])
    row['current_bucket_median_ms'] = median(row['current_bucket_ms'])
backend = [json.loads((profile_root / case / 'cache-update.json').read_text())
           for case in ('valkey-full', 'tpcc-bcco-2m')]
result = dict(date='2026-09-28', baseline_commit='8b67cade6017ac8e3ccff242a208c5dc025380ea',
              selection=selection, backend_cache_prototypes=backend, ui_computation_prototypes=ui,
              evidence_paths=[str(selection_root), str(profile_root)],
              scope='Retained-trace analysis and offline prototypes, not end-to-end browser speedups.')
a.out.write_text(json.dumps(result, indent=2) + '\n')
for case in selection:
    print(case['name'])
    for row in case['summary']:
        print(row)
