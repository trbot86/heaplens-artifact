#!/usr/bin/env python3
"""Regenerate adopted paper tables from small saved evidence; standard library only."""
import argparse
import json
import math
from pathlib import Path
import statistics as stats

HERE=Path(__file__).resolve().parent
APPS=('ascylib_efrb','ascylib_dvy','tpcc_bcco','tpcc_efrb','rocks_hsl','rocks_isl','valkey','hnsw128','hnsw1536')
ARMS=('full','no_per_time','no_coverage_first','no_alternation')

def wait_percent(row):
    waits=row['waits']
    if row['identity']['application']=='valkey':
        if any(w['reuse_ns'] or w['reuse_count'] for w in waits):
            raise ValueError('Nonzero Valkey waits need an explicit phase denominator')
        return 0.0
    workers=[w for w in waits if w['phase']==1 and w['begin_ns']>0]
    if not workers: raise ValueError('Missing measured worker interval')
    if any(not 0<=w['reuse_ns']<=w['end_ns']-w['begin_ns'] for w in workers):
        raise ValueError('Invalid worker wait interval')
    return 100*sum(w['reuse_ns'] for w in workers)/sum(w['end_ns']-w['begin_ns'] for w in workers)

def logging_summary(rows):
    result={}
    for app in APPS:
        groups={arm:[x for x in rows if x['identity']['application']==app and x['identity']['arm']==arm]
                for arm in ('plain','logging','fixed2')}
        for arm in ('plain','logging'):
            if sorted(x['identity']['round'] for x in groups[arm])!=list(range(1,11)):
                raise ValueError(f'{app}/{arm}: expected exactly ten distinct rounds')
        plain=stats.mean(x['throughput'] for x in groups['plain'])
        logged=stats.mean(x['throughput'] for x in groups['logging'])
        out=dict(plain_mean=plain,logging_mean=logged,loss_percent=100*(1-logged/plain),
                 wait_percent=stats.mean(wait_percent(x) for x in groups['logging']),
                 cohort=groups['plain'][0]['cohort'])
        if app=='tpcc_bcco':
            fixed=groups['fixed2']
            if sorted(x['identity']['round'] for x in fixed)!=list(range(1,11)): raise ValueError('fixed2 rounds')
            f=stats.mean(x['throughput'] for x in fixed)
            out['buffer_ablation']=dict(fixed_mean=f,fixed_loss_percent=100*(1-f/plain),
                adaptive_gain_percent=100*(logged/f-1),fixed_wait_percent=stats.mean(map(wait_percent,fixed)),
                fixed_mean_peak_rss_gib=stats.mean(x['peak_rss_kib']/1024**2 for x in fixed),
                adaptive_mean_peak_rss_gib=stats.mean(x['peak_rss_kib']/1024**2 for x in groups['logging']))
            out['abort_attempt_percent']={arm:stats.mean(100*x['transactions_aborted']/(
                x['transactions_aborted']+x['transactions_committed']) for x in groups[arm])
                for arm in ('plain','fixed2','logging')}
        if app=='rocks_hsl':
            out['alternative_timing']={arm:{k:stats.mean(x['hsl_timing'][k] for x in groups[arm])
                for k in ('reader_only_throughput','native_exact_elapsed_seconds','reader_only_elapsed_seconds',
                          'writer_elapsed_seconds','writer_completion_from_reader_start_seconds','writer_tail_after_readers_seconds')}
                for arm in ('plain','logging')}
            out['alternative_timing']['reader_only_loss_percent']=100*(1-
                out['alternative_timing']['logging']['reader_only_throughput']/
                out['alternative_timing']['plain']['reader_only_throughput'])
        result[app]=out
    return result

def gm(xs):
    if not xs or any(x<0 for x in xs): raise ValueError('Invalid geometric mean')
    return 0.0 if 0 in xs else math.exp(stats.mean(map(math.log,xs)))

def selection_summary(cells):
    if len(cells)!=208: raise ValueError('Expected 13 patterns x 2 settings x 2 budgets x 4 arms')
    if len({(x['application'],x['pattern'],tuple(x['sampling']),x['page_budget'],x['arm']) for x in cells})!=208:
        raise ValueError('Duplicate pattern cells')
    if any(x['completed']!=20 or x['expected']!=20 or x['pattern_absent'] for x in cells):
        raise ValueError('Incomplete/absent targets must be reported separately')
    table=[]
    for budget in (128,32):
        for p in (1,.1):
            xs=[x for x in cells if x['page_budget']==budget and x['sampling']==[p,1] and
                x['arm']=='full' and x['application']!='rare-isl']
            assert len(xs)==12
            table.append(dict(p=p,page_budget=budget,patterns_found_in_all_20=sum(x['grid']==20 for x in xs),
                patterns=12,duration_coverage_percent=100*gm([x['duration_coverage_mean'] for x in xs])))
    ablations=[]
    for rare in (False,True):
        for budget in (128,32):
            xs=[x for x in cells if x['page_budget']==budget and (rare or x['application']!='rare-isl')]
            means={arm:gm([x['duration_coverage_mean'] for x in xs if x['arm']==arm]) for arm in ARMS}
            ablations.append(dict(rare_included=rare,page_budget=budget,arms={arm:dict(
                duration_coverage_percent=100*means[arm],
                full_relative_gain_percent=100*(means['full']/means[arm]-1)) for arm in ARMS}))
    return dict(table4=table,ablations=ablations)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json',action='store_true',help='Print full unrounded summaries')
    args=parser.parse_args()
    logging=logging_summary(json.loads((HERE/'logging-cells.json').read_text())['cells'])
    selection=selection_summary(json.loads((HERE/'selection-summary.json').read_text())['cells'])
    if args.json: print(json.dumps(dict(logging=logging,selection=selection),indent=2,allow_nan=False));return
    print('Table 3: application | plain Kops/s | logging Kops/s | loss % | worker wait %')
    for app,x in logging.items():
        pct=lambda v: '0.0' if v==0 else format(v,'.2g')
        print(f"{app} | {x['plain_mean']/1000:.3g} | {x['logging_mean']/1000:.3g} | {pct(x['loss_percent'])} | {pct(x['wait_percent'])}")
    a=logging['tpcc_bcco']['buffer_ablation']
    print(f"BCCO adaptive gain {a['adaptive_gain_percent']:.1f}%; loss {a['fixed_loss_percent']:.1f} -> {logging['tpcc_bcco']['loss_percent']:.1f}%; mean peak RSS delta {a['adaptive_mean_peak_rss_gib']-a['fixed_mean_peak_rss_gib']:.1f} GiB")
    print('Table 4: p | page budget | patterns found in all 20 | duration coverage %')
    for x in selection['table4']:
        print(f"{x['p']:g} | {x['page_budget']} | {x['patterns_found_in_all_20']}/12 | {x['duration_coverage_percent']:.1f}")

if __name__=='__main__': main()
