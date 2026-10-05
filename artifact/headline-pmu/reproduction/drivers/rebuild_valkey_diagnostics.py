"""Container-side rebuild of a private copied baseline logging tree only."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import hashlib
import argparse
import json
from pathlib import Path
import subprocess
from valkey_readiness_diagnostics import io_diagnostics,bio_diagnostics
from valkey_readiness_drain import transform as drain

parser=argparse.ArgumentParser()
parser.add_argument('--variant',choices=['baseline','optimized'],default='baseline')
variant=parser.parse_args().variant
root=Path('/build')/f'{variant}-logging'
manifest=json.loads((root/'preparation.json').read_text())
changes=[]
for name,transform in [('io_threads.c',io_diagnostics),('bio.c',bio_diagnostics)]:
    path=root/'work-valkey/src'/name
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    updated=transform(path.read_text())
    if name=='io_threads.c': updated=drain(updated)
    path.write_text(updated)
    changes.append(dict(path=str(path),before=before,after=hashlib.sha256(path.read_bytes()).hexdigest()))
command=['make','-j8','MALLOC=jemalloc','BUILD_TLS=no','BUILD_RDMA=no','BUILD_LUA=no','USE_SYSTEMD=no','V=1',
    f'SERVER_CFLAGS=-D_GNU_SOURCE -D_DEFAULT_SOURCE -DHEAPLENS_VALKEY_SEMANTIC_ALLOC -I{root}/toolchain/memhook']
with (root/'readiness-rebuild.log').open('x') as log:
    subprocess.run(command,cwd=root/'work-valkey',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
manifest['readiness_diagnostics']=changes
manifest['readiness_build_command']=command
manifest['binaries']={path:hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in manifest['binaries']}
(root/'preparation.json').write_text(json.dumps(manifest,indent=2)+'\n')
