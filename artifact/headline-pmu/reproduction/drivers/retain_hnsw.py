"""Post-exit full typed audit then verified retention; caller holds host lock."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
from portable_runtime import expected_traces
import hashlib,json,re,struct,sys
from collections import Counter
from pathlib import Path
from audit_hnsw import audit
from trace_store import TraceStore,write_json
H=Path('/campaign/data')
B=Path('/campaign/archive')

def typed_scan(dest):
    types={int(line.split('|',1)[0]):line.split('|',1)[1] for line in (dest/'typeset_dump.txt').read_text().splitlines() if '|' in line}
    counts=Counter()
    with (dest/'events.bin').open('rb') as raw:
        for block in iter(lambda:raw.read(40*65536),b''):
            if len(block)%40:raise ValueError('partial event')
            for tid,op in struct.iter_unpack('<34xHB3x',block):
                if op not in (0,1):raise ValueError('invalid operation')
                if op:
                    if tid not in types:raise ValueError('unknown allocation type')
                    counts[types[tid]]+=1
    for suffix in ('VectorPayload','VisitedMass','VisitedList','QueryScratch'):
        if not any(name.endswith(suffix) and n>0 for name,n in counts.items()):raise ValueError('missing '+suffix)
    if sum(n for name,n in counts.items() if name.endswith('VectorPayload'))!=1000000:raise ValueError('vector count')
    return dict(counts)

def main():
    trial=sys.argv[1]
    if not re.fullmatch(r'paper-hnsw-d(128|1536)-(baseline|optimized)-logging-r(0[1-9]|10)',trial):raise ValueError('trial identity')
    dest=H/'hnsw-paper'/trial
    checked=audit(dest);state=json.loads((dest/'result.json').read_text())
    expected=f"paper-hnsw-d{state['dim']}-{state['variant']}-{state['arm']}-r{state['rep']:02d}"
    if trial!=expected:raise ValueError('identity mismatch')
    checked['typed_allocations']=typed_scan(dest)
    checked['semantic_scope']='graph regions, visited buffers and dynamic query C++ scratch; not exhaustive Python allocations'
    target=dest/'measurement-audit.json'
    if target.exists():raise FileExistsError('preserve prior audit')
    write_json(target,checked)
    modules=[digest for path,digest in state['build']['binaries'].items() if '/source/hnswlib' in path]
    if len(modules)!=1:raise ValueError('one module identity')
    identity=dict(trial_id=trial,measurement_status='completed',application='hnsw',variant=state['variant'],
        repetition=state['rep'],dimension=state['dim'],source_revision=state['build']['source_revision'],
        binary_sha256=modules[0],binary_manifest=state['build']['binaries'],
        command_sha256=hashlib.sha256(json.dumps(state['command']).encode()).hexdigest(),
        operations=500000,semantic_audit_status='source_path_final_audit_separate')
    store=TraceStore(raw_root=H/'hnsw-paper',archive_root=B/'archives-hnsw-paper',
        manifest_root=H/'trace-manifests-hnsw-paper',campaign='headline-hnsw-20261001',host=host_name(),expected_traces=expected_traces(('hnsw',)))
    print(json.dumps(store.archive(trial,identity),indent=2))

if __name__=='__main__':main()
