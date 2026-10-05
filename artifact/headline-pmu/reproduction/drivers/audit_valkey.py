"""Independent post-exit checks; no benchmark execution or raw deletion."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import csv
import json
import math
from pathlib import Path

EVENTS={'cycles','instructions','cache-misses','dTLB-load-misses'}


def require(condition, message):
    if not condition: raise ValueError(message)


def counter_rows(path):
    result={}
    for row in csv.reader(Path(path).read_text().splitlines()):
        if len(row)<3 or row[2] not in EVENTS: continue
        require(row[2] not in result,'duplicate counter')
        count,runtime,coverage=float(row[0]),float(row[3]),float(row[4])
        require(all(math.isfinite(x) for x in (count,runtime,coverage)), 'nonfinite counter')
        require(count>=0 and runtime>0 and 99<=coverage<=100,'counter coverage/count')
        result[row[2]]=dict(scaled_count=count,runtime_ns=runtime,running_percent=coverage)
    require(set(result)==EVENTS,'missing counter')
    return result


def producer_reports(lines,lo,hi,size):
    producers=[json.loads(x[12:]) for x in lines if x.startswith('HL_PRODUCER ')]
    waits=[json.loads(x[15:]) for x in lines if x.startswith('HL_WINDOW_WAIT ')]
    tids={x['tid'] for x in producers}
    require(len(producers)==len(tids)==29,'producer completeness')
    require(len(waits)==58 and {x['tid'] for x in waits}==tids,'wait completeness')
    require(size>0 and size%40==0,'raw record alignment')
    require(all(x['record_bytes']==40 and isinstance(x['records'],int) and x['records']>=0 for x in producers),'producer records')
    require(sum(x['records']*40 for x in producers)==size,'producer byte reconciliation')
    for tid in tids:
        rows=[x for x in waits if x['tid']==tid]
        require(sorted(x['kind'] for x in rows)==[0,1],'wait kinds')
        require(rows[0]['stored_events']==rows[1]['stored_events']<=4096,'event store completeness')
        for row in rows:
            require(row['lo']==lo and row['hi']==hi,'wait phase boundary')
            require(all(isinstance(row[k],int) and row[k]>=0 for k in
                        ('starts','overlap_ns','max_overlap_ns','errors_starting','crosses_begin','crosses_end','stored_events')),'wait values')
            require(row['errors_starting']==0,'wait error')
            require(row['max_overlap_ns']<=row['overlap_ns']<=hi-lo,'wait overlap bounds')
    return dict(producers=producers,waits=waits,raw_bytes=size)


def audit(dest, *, archived_raw_bytes=None):
    dest=Path(dest)
    state=json.loads((dest/'result.json').read_text())
    require(state['status']=='completed_pending_independent_audit','incomplete trial')
    require(state['trial']==dest.name=='paper-valkey-%s-%s-r%02d'%(state['variant'],state['arm'],state['rep']),'trial identity')
    for cmd in (state['preload_command'],state['client_command']):
        require(all(x in cmd for x in ('--physcpubind='+cpus(24,1),'--membind='+str(node(1)),'--threads=24','--clients=4','--pipeline=16','--key-minimum=1','--key-maximum=4000000','--data-size=128','--distinct-client-seed')),'client configuration')
    require(all(x in state['preload_command'] for x in ('--ratio=1:0','--key-pattern=P:P','--requests=allkeys')),'preload configuration')
    require(all(x in state['client_command'] for x in ('--ratio=1:4','--key-pattern=R:R','--test-time=30')),'measured configuration')
    enable,disable=state['enable'],state['disable']
    require(enable['action']=='enable' and disable['action']=='disable','gate actions')
    require(enable['before_ns']<=enable['after_ns']<disable['before_ns']<=disable['after_ns'],'gate ordering')
    totals=json.loads((dest/'benchmark.json').read_text())['ALL STATS']['Totals']
    require(totals==state['client_totals'],'denominator source mismatch')
    require(totals['Count']>0 and totals['Connection Errors']==0 and totals['Misses/sec']==0,'workload errors')
    result=dict(trial=dest.name,operations=totals['Count'],counters=counter_rows(dest/'perf.csv'),
                status='measurement_checks_passed_source_semantic_audit_separate')
    if state['arm']=='logging':
        if archived_raw_bytes is not None:
            require(not (dest/'events.bin').exists(),'archived raw unexpectedly present')
        result.update(producer_reports((dest/'server.log').read_text().splitlines(),
            enable['before_ns'],disable['after_ns'],archived_raw_bytes if archived_raw_bytes is not None else (dest/'events.bin').stat().st_size))
    return result


if __name__=='__main__':
    import sys
    print(json.dumps(audit(sys.argv[1]),indent=2))
