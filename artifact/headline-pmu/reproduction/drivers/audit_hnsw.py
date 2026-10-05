"""Independent headline identity, denominator, PMU and producer reconciliation."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import hashlib,json
from pathlib import Path
from audit_valkey import require,counter_rows

def audit(path, receipt=None):
    path=Path(path); state=json.loads((path/'result.json').read_text())
    require(state['scope']=='headline' and state['status']=='passed_runner_checks','headline successful runner')
    lines=(path/'stderr.log').read_text().splitlines()
    def rows(prefix):return [json.loads(line[len(prefix):]) for line in lines if line.startswith(prefix)]
    results=[json.loads(line) for line in (path/'stdout.log').read_text().splitlines() if line.startswith('{') and '"timed_queries"' in line]
    require(len(results)==1,'unique benchmark result'); result=results[0]
    expected=dict(elements=1000000,queries=100000,warmup=10000,iterations=5,timed_queries=500000,
        threads=24,build_threads=24,m=16,ef_construction=200,ef=64,k=10,query_mode='indexed',deleted=0,
        dim=state['dim'],variant=state['variant'],repetition=state['rep'])
    for key,value in expected.items():require(result[key]==value,'configuration '+key)
    require(state['build']['allocator']=='system libc','allocator')
    require(state['build']['source_revision']=='7f4f5f20125ad0a2571abc8ddb0e98e13c7ae109','revision')
    require(result['defines']==','.join(state['build']['defines']),'defines')
    command=state['command']; require(command[command.index('--seed')+1]=='1','seed')
    require(command[command.index('--physcpubind='+cpus(24))+1]=='--membind='+str(node(0)),'NUMA')
    windows=rows('HL_HNSW_WINDOW '); workers=rows('HL_HNSW_WORKER ')
    require([row['iteration'] for row in windows]==list(range(1,6)),'five measured windows')
    previous=0
    for row in windows:
        enable,disable=row['enable'],row['disable']
        require(enable['action']=='enable' and disable['action']=='disable','gate actions')
        require(previous<enable['before_ns']<=enable['after_ns']<disable['before_ns']<=disable['after_ns'],'ordered gate bounds')
        previous=disable['after_ns']
        selected=[w for w in workers if w['iteration']==row['iteration'] and w['phase']==1]
        require(len(selected)==48,'24 measured worker pairs')
        for worker in range(24):
            pair=[w for w in selected if w['worker']==worker]
            require(len(pair)==2 and {w['boundary'] for w in pair}=={'begin','end'},'paired boundaries')
            require(len({w['tid'] for w in pair})==1,'paired thread identity')
    report=dict(status='passed_measurement_checks_semantics_separate',configuration=expected,
                counters=counter_rows(path/'perf.csv'),windows=windows)
    if state['arm']=='logging':
        waits=rows('HL_WAIT ')
        if receipt is None:
            size=(path/'events.bin').stat().st_size
        else:
            identity=receipt['identity']
            require(receipt['status']=='archived_raw_removed','completed retention')
            require(identity['trial_id']==path.name,'receipt trial')
            for key,value in dict(variant=state['variant'],repetition=state['rep'],dimension=state['dim'],operations=500000).items():
                require(identity[key]==value,'receipt identity '+key)
            require(identity['binary_manifest']==state['build']['binaries'],'receipt binary manifest')
            require(identity['command_sha256']==hashlib.sha256(json.dumps(command).encode()).hexdigest(),'receipt command')
            require(identity['source_revision']==state['build']['source_revision'],'receipt revision')
            require(receipt['original_raw_path']==str(path/'events.bin'),'receipt raw path')
            require(not (path/'events.bin').exists(),'archived raw removed')
            archive=Path(receipt['archive_path'])
            require(archive.is_file() and archive.stat().st_size==receipt['archive_bytes'],'retained archive size')
            require(receipt['records']*40==receipt['raw_bytes'],'receipt record bytes')
            size=receipt['raw_bytes']
        require(size>0 and size%40==0,'raw alignment')
        require(sum(row['records'] for row in waits)*40==size,'all producer bytes')
        require(len({(row['tid'],row['phase']) for row in waits})==len(waits),'unique reports')
        measured={w['tid'] for w in workers if w['phase']==1}
        require(len(measured)==120,'fresh measured workers')
        require(measured<={w['tid'] for w in waits if w['phase']==1},'measured reports')
        require(all(w['reuse_errors']==w['shutdown_errors']==0 for w in waits),'wait errors')
        report.update(raw_bytes=size,wait_rows=len(waits),measured_producers=len(measured))
    return report

if __name__=='__main__':
    import sys
    print(json.dumps(audit(sys.argv[1]),indent=2))
