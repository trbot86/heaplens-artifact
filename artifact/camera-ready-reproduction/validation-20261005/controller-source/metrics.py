"""Recompute paper-facing statistics from retained or newly generated rows."""
import collections
import json
import math
from pathlib import Path
from statistics import median


def read(path):
    return json.loads(Path(path).read_text())


def jsonlines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def backend(rows):
    expected = {(case, spatial, policy, rep) for case in ('valkey', 'bcco')
                for spatial in ('enumerated', 'range') for policy in ('direct', 'prefix')
                for rep in (-1, 0, 1, 2)}
    identities = [(r['case'], r['spatial'], r['policy'], r['rep']) for r in rows]
    if len(identities) != len(expected) or set(identities) != expected:
        raise ValueError('Incomplete or duplicate backend matrix')
    if any(r['status']!='complete' for r in rows):raise ValueError('Failed backend trial')
    result = []
    for case in ('valkey', 'bcco'):
        if len({r['payload_sha256'] for r in rows if r['case'] == case}) != 1:
            raise ValueError('Backend complete-output hashes differ')
        for spatial, policy in [('enumerated','direct'),('range','direct'),('enumerated','prefix'),('range','prefix')]:
            group = [r for r in rows if (r['case'],r['spatial'],r['policy']) == (case,spatial,policy) and r['rep'] >= 0]
            if not all(r['status'] == 'complete' for r in group):
                raise ValueError('Failed backend trial')
            result.append(dict(case=case, spatial=spatial, temporal=policy, trials=3,
                cache_seconds=median(r['phases']['cache'] for r in group),
                preparation_seconds=median(r['total_seconds'] for r in group)))
    return result


def toggle(rows,policies=('baseline','optimized')):
    result = []
    for name, budget in [('valkey-full',52),('tpcc-bcco-2m',17),('tpcc-bcco-2m',128)]:
        values = {}
        for policy in policies:
            group = [r for r in rows if (r['name'],r['budget'],r['policy']) == (name,budget,policy)]
            if len(group) != 3 or {r['rep'] for r in group} != {0,1,2} or any(r['errors'] for r in group):
                raise ValueError('Incomplete or failed UI toggle trials')
            trials = []
            for row in group:
                times = [e['ms'] for e in row['metrics']['events'] if e['kind']=='response'
                         and e['action'].startswith('cache-visibility-') and e['type']=='click']
                if not times: raise ValueError('Missing cache toggle timing')
                trials.append(median(times))
            values[policy] = dict(milliseconds=median(trials), trial_medians_ms=trials)
        for rep in range(3) if len(policies)==2 else ():
            pair = [r for r in rows if (r['name'],r['budget'],r['rep']) == (name,budget,rep)]
            if len(pair) != 2 or pair[0]['states'] != pair[1]['states'] or pair[0]['exports'] != pair[1]['exports']:
                raise ValueError('UI rendered states or text exports differ')
        result.append(dict(case=name, pages=budget, **values))
    if len(rows) != 9*len(policies): raise ValueError('Unexpected UI toggle trial count')
    return result


def detail(before, after):
    for rows in (before,after) if before is not None else (after,):
        finals=[r for r in rows if r.get('checkpoint')=='final']
        if len(finals)!=9:raise ValueError('Unexpected detail final-row count')
    result = []
    for name, baseline_rects in [('dense64k',65538),('dense1m',65538),('live1m',7815)]:
        values = {}
        for policy, rows in ([('baseline',before)] if before is not None else [])+[('optimized',after)]:
            finals = [r for r in rows if r.get('checkpoint')=='final' and r['rep']>=0 and r['name']==name]
            if len(finals)!=3 or {r['rep'] for r in finals}!={0,1,2}:
                raise ValueError('Incomplete or duplicate detail trials')
            trials = []
            for row in finals:
                if row['status']!='complete' or row['errors']: raise ValueError('Failed detail trial')
                actions = [a for a in row['actions'] if a['label']=='brush-64k']
                if len(actions)!=1: raise ValueError('Missing unique detail selection')
                action = actions[0]
                ui = action['state']['ui']
                if ui['selected_region_bytes'] != 65536 or ui['detailRects'] != (2050 if policy=='optimized' else baseline_rects):
                    raise ValueError('Incorrect detail selection or rectangle count')
                times = [e['ms'] for e in action['events'] if e['kind']=='response' and e['type']=='pointerup']
                if not times: raise ValueError('Missing detail timing')
                trials.append(median(times))
            values[policy] = dict(milliseconds=median(trials), trial_medians_ms=trials)
        result.append(dict(case=name, selected_bytes=65536, **values))
    return result


def sampling(rows, efrb):
    settings = {(0.001,1),(0.01,1),(0.1,1),(0.1,2),(1.0,1)}
    expected = {(p,s,seed) for p,s in settings for seed in range(20260928,20260948)}
    if len(rows)!=100 or {(r['p'],r['s'],r['seed']) for r in rows}!=expected:
        raise ValueError('Incomplete or duplicate sampling matrix')
    result = []
    for p,s in sorted(settings):
        group = [r for r in rows if (r['p'],r['s'])==(p,s)]
        if any(r['minimum_violations'] or r['displayed_pages']>128 or r['prepared_records']>100000 for r in group):
            raise ValueError('Sampling floor or display budget violation')
        result.append(dict(p=p,s=s,trials=20,rax_retained=sum(bool(r['display_success']) for r in group),
                           robj_retained=sum(bool(r['original_robj_success']) for r in group)))
    if len(efrb)!=20 or {r['seed'] for r in efrb}!=set(range(20260928,20260948)):
        raise ValueError('Incomplete EFRB selection matrix')
    if any(len(r['displayed_pages'])>128 for r in efrb):raise ValueError('EFRB display budget violation')
    return dict(valkey=result,efrb=dict(trials=20,retained=sum(bool(r['displayed_qualifying_pages']) for r in efrb)))


def saved(root):
    root = Path(root)
    return dict(backend=backend(read(root/'backend.json')),
                ui_toggle=toggle(jsonlines(root/'toggle.jsonl')),
                ui_detail=detail(jsonlines(root/'detail-baseline.jsonl'),jsonlines(root/'detail-optimized.jsonl')),
                sampling=sampling(read(root/'sampling.json'),[read(root/f'efrb-{r:02d}.json') for r in range(20)]),
                application_references=application_references(root))


def application_references(root):
    """Arithmetic from frozen audit means, not a fresh audit of raw trials."""
    named=read(root/'named-final-audit.json');apps=read(root/'application-final-audit.json')
    overhead=read(root/'overhead-final-audit.json')
    if any(x['status']!='passed' for x in (named,apps,overhead)):
        raise ValueError('Failed saved audit')
    pairs=[]
    def add(study,means,before,after):
        b,a=means[before],means[after]
        if not all(math.isfinite(v) and v>0 for v in (b,a)):raise ValueError('Invalid audit mean')
        pairs.append(dict(study=study,before=before,after=after,baseline_mean=b,
                          optimized_mean=a,gain_percent=100*(a/b-1)))
    controls={'ascylib_efrb_bench':'a_default','ascylib_dvy_bench':'a_96B_default',
              'ascylib_hj_bench':'jemalloc','tpcc_bcco_bench':'a_default','tpcc_efrb_bench':'b_mimalloc'}
    for row in named['experiments']:
        name=next(n for n in controls if row['experiment'].startswith(n+'-'))
        for variant in row['means']:
            if variant!=controls[name]:add(name,row['means'],controls[name],variant)
        if name=='tpcc_bcco_bench':add(name,row['means'],'c_seg_ds_pack_lock','e_combined_single_recmgr')
    for name,row in apps['experiments'].items():
        means=row.get('mean_qps',row.get('means'))
        if name=='final-hnsw':
            for dim in (128,1536):add(name,means,f'{dim}/baseline',f'{dim}/vector_huge')
        elif name.startswith('factor-'):
            dim=name.rsplit('-',1)[1];before=dim+('/packed' if 'alignment' in name else '/baseline')
            for variant in means:
                if variant!=before:add(name,means,before,variant)
            if 'alignment' in name:add(name,means,f'{dim}/separated_unaligned32',f'{dim}/separated_aligned64')
        else:add(name,means,'baseline','B1C1_64' if name=='final-valkey' else 'optimized')
    for row in overhead['summary']:
        expected=100*(1-row['logging_ops_s']/row['baseline_ops_s'])
        if not math.isclose(expected,row['throughput_reduction_pct'],abs_tol=1e-9):
            raise ValueError('Overhead percentage differs from audit means')
    return dict(scope='Recomputed ratios from retained independent-audit means; no new raw-trial audit',
                comparisons=pairs,stock_logging_overhead=overhead['summary'])


def backend_current(rows):
    expected={(case,rep) for case in ('valkey','bcco') for rep in (-1,0,1,2)}
    if len(rows)!=8 or {(r['case'],r['rep']) for r in rows}!=expected:
        raise ValueError('Incomplete current backend trials')
    result=[]
    for case in ('valkey','bcco'):
        group=[r for r in rows if r['case']==case]
        if any(r['status']!='complete' or r['spatial']!='range' or r['policy']!='prefix' for r in group):
            raise ValueError('Invalid current backend trial')
        if len({r['payload_sha256'] for r in group})!=1:raise ValueError('Current backend output differs across trials')
        measured=[r for r in group if r['rep']>=0]
        result.append(dict(case=case,trials=3,cache_seconds=median(r['phases']['cache'] for r in measured),
                           preparation_seconds=median(r['total_seconds'] for r in measured)))
    return result
