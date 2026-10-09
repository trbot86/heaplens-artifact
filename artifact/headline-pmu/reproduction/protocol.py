"""Pure schedule, source materialization and topology helpers (no workloads)."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath

REVISION = '7f4f5f20125ad0a2571abc8ddb0e98e13c7ae109'
APPLICATIONS = ('ascylib_efrb','ascylib_dvy','ascylib_hj','tpcc_bcco','tpcc_efrb',
                'rocks_hsl','rocks_isl','valkey','hnsw128','hnsw1536')


def schedule(apps=APPLICATIONS, repetitions=10, arms='both'):
    if not apps or len(set(apps))!=len(apps) or set(apps)-set(APPLICATIONS):
        raise ValueError('Select unique supported applications')
    if not 1 <= repetitions <= 10:
        raise ValueError('Repetitions must be between 1 and 10')
    if arms not in ('both', 'plain'):
        raise ValueError('Select both arms or plain only')
    cells=[]
    for family in ('ascylib','tpcc','rocks','valkey','hnsw'):
        selected=[a for a in APPLICATIONS if a in apps and a.startswith(family)]
        for rep in range(1,repetitions+1):
            order=[('before','plain'),('before','logging'),('after','plain'),('after','logging')]
            offset=(rep-1)%4
            order=order[offset:]+order[:offset]
            if ((rep-1)//4)%2:order.reverse()
            if arms == 'plain':
                # Alternate AB/BA directly; filtering the four-arm rotation
                # alone would give unequal first-position counts over ten blocks.
                order=[('before','plain'),('after','plain')]
                if rep % 2 == 0:order.reverse()
            for app in selected:
                for variant,arm in order:
                    cells.append(dict(id=f'{app}-{variant}-{arm}-r{rep:02d}',application=app,
                                      family=family,variant=variant,arm=arm,repetition=rep))
    return cells


def source_bytes(root, bundle, name, entry):
    path=(bundle/'blobs'/(entry['sha256']+'.blob')) if entry['override'] else root/name
    data=path.read_bytes()
    # A Git checkout on Windows may convert text to CRLF. The materialized
    # Linux source still has to match the exact historical Git bytes.
    if hashlib.sha256(data).hexdigest()!=entry['sha256']:
        data=data.replace(b'\r\n', b'\n')
    if hashlib.sha256(data).hexdigest()!=entry['sha256'] or len(data)!=entry['bytes']:
        raise ValueError('Historical source mismatch: '+name)
    return data


def materialize(root, bundle, destination):
    manifest=json.loads((bundle/'source-manifest.json').read_text())
    if manifest['revision']!=REVISION:raise ValueError('Unexpected source revision')
    destination.mkdir()  # never merge with an existing build/source
    for name,entry in manifest['files'].items():
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe manifest path')
        target=destination/name
        target.parent.mkdir(parents=True,exist_ok=True)
        if entry['kind']=='symlink':
            link=entry['target']
            resolved=posixpath.normpath(posixpath.join(posixpath.dirname(name),link))
            if link.startswith('/') or resolved=='..' or resolved.startswith('../'):
                raise ValueError('Unsafe source symlink')
            target.symlink_to(link)
        else:
            target.write_bytes(source_bytes(root,bundle,name,entry))
            target.chmod(entry['mode'])
    return manifest['revision']


def topology(text, allowed, server_node=0, client_node=1, apps=APPLICATIONS):
    entries=[]
    for line in text.splitlines():
        if not line or line.startswith('#'):continue
        cpu,node,socket,core,online=line.split(',')
        if online=='Y' and int(cpu) in allowed and node not in ('','-'):
            entries.append((int(cpu),int(node),socket,core))
    result=[]
    for wanted in (server_node,client_node):
        physical={}
        for cpu,n,socket,core in sorted(entries):
            if n==wanted:physical.setdefault((socket,core),cpu)
        result.append(dict(node=wanted,cpus=list(physical.values())))
    need=24 if any(a.startswith(('tpcc','hnsw')) or a in ('valkey','ascylib_hj') for a in apps) else 0
    for app,n in (('ascylib_efrb',4),('ascylib_dvy',8),('rocks_isl',20)):
        if app in apps:need=max(need,n)
    if len(result[0]['cpus'])<need:raise ValueError(f'Server node needs {need} distinct allowed physical cores')
    if 'valkey' in apps and (server_node==client_node or len(result[1]['cpus'])<24):
        raise ValueError('Valkey needs 24 physical client cores on a separate NUMA node')
    # HSL retains 96 total workers, distributed evenly across two NUMA nodes;
    # physical cores precede SMT siblings. Record the selected logical IDs.
    rocks=[]
    if 'rocks_hsl' in apps:
        if server_node==client_node:raise ValueError('HSL needs two distinct NUMA nodes')
        for selected in result:
            all_cpus=sorted(cpu for cpu,n,_,_ in entries if n==selected['node'])
            ordered=selected['cpus']+[cpu for cpu in all_cpus if cpu not in selected['cpus']]
            if len(ordered)<48:raise ValueError('HSL needs 48 allowed logical CPUs on each selected node')
            rocks.extend(ordered[:48])
    return dict(nodes=result,rocks_cpus=rocks)
