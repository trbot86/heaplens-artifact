"""Post-exit only. Caller holds experiment lock and verifies no timed process.

Archives exactly one successfully checked logging cell; never retries a receipt.
Source/semantic audit remains separate from this mechanical retention check.
"""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
from portable_runtime import expected_traces
import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from audit_valkey import audit
from trace_store import TraceStore, write_json

HOME=Path('/campaign/data')
BASE=Path('/campaign/archive')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('trial')
    args=parser.parse_args()
    if '/' in args.trial or not args.trial.startswith('paper-valkey-'):
        raise ValueError('unsafe trial identity')
    dest=HOME/'valkey-paper'/args.trial
    checked=audit(dest)
    state=json.loads((dest/'result.json').read_text())
    if state['arm']!='logging': raise ValueError('not a logging cell')
    stage='valkey-readiness-build2' if state['variant']=='baseline' else 'valkey-readiness-build4'
    type_path=Path('/build')/(state['variant']+'-logging')/'typeset_dump.txt'
    type_text=type_path.read_text()
    types={int(line.split('|',1)[0]):line.split('|',1)[1] for line in type_text.splitlines() if '|' in line}
    counts=Counter()
    with (dest/'events.bin').open('rb') as raw:
        for block in iter(lambda:raw.read(40*65536),b''):
            if len(block)%40: raise ValueError('partial typed event')
            for type_id,allocated in struct.iter_unpack('<34xHB3x',block):
                if allocated not in (0,1): raise ValueError('invalid event kind')
                if allocated: counts[types.get(type_id,'UNKNOWN:'+str(type_id))]+=1
    if not counts.get('robj') or any(name.startswith('UNKNOWN:') for name in counts):
        raise ValueError('missing semantic objects or unknown allocated type')
    checked['typed_allocations']=dict(counts)
    checked['typed_scope']='full raw event type reconciliation; source-path coverage audit remains separate'
    with (dest/'typeset_dump.txt').open('x') as output: output.write(type_text)
    audit_path=dest/'measurement-audit.json'
    if audit_path.exists(): raise FileExistsError('preserve existing audit; reconcile explicitly')
    write_json(audit_path,checked)
    binary='/build/'+state['variant']+'-logging/work-valkey/src/valkey-server'
    identity=dict(trial_id=args.trial,measurement_status='completed',application='valkey',
        variant=state['variant'],repetition=state['rep'],
        source_revision='7f4f5f20125ad0a2571abc8ddb0e98e13c7ae109',
        binary_sha256=state['build']['binaries'][binary],
        command_sha256=hashlib.sha256(json.dumps(state['server_command']).encode()).hexdigest(),
        client_sha256=state['client_sha256'],operations=checked['operations'],
        semantic_audit_status='separate_pending')
    store=TraceStore(raw_root=HOME/'valkey-paper',archive_root=BASE/'archives-valkey-paper',
        manifest_root=HOME/'trace-manifests-valkey-paper',campaign='headline-valkey-20261001',
        host=host_name(),expected_traces=expected_traces(('valkey',)))
    receipt=store.archive(args.trial,identity)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__': main()
