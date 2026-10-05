"""Build paired source-matched ASCYLIB headline variants, without running trials."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

CONTROL=Path('/control/drivers')
ROOT=Path('/root/sifter')
BUILD=Path('/build')
SPECS={
 'efrb': dict(tree='bst-ellen',binary='lf-bst_ellen',threads=4,initial=262144,
              flags=['STM=LOCKFREE','SET_CPU=0'],optimized=['SEG_OBJS=1','INIT=all'],memory='interleave'),
 'dvy': dict(tree='bst-drachsler',binary='lb-bst-drachsler',threads=8,initial=1048576,
             flags=['VERSION=O2','SET_CPU=0'],optimized=['DRACHSLER_PAD=192'],memory='interleave'),
 'hj': dict(tree='bst-howley',binary='lf-bst-howley',threads=24,initial=1048576,
            flags=['STM=LOCKFREE','SET_CPU=0'],optimized=[],memory='membind'),
}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def replace(path, old, new):
    before=path.read_text()
    if before.count(old)!=1: raise RuntimeError(f'Unexpected source anchor: {path}: {old!r}')
    after=before.replace(old,new);path.write_text(after)
    with (BUILD/'overlays.diff').open('a') as f:
        f.writelines(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=str(path),tofile=str(path)))
def run(cmd,cwd=ROOT,env=None):
    print('BUILD',list(map(str,cmd)),flush=True)
    subprocess.run(list(map(str,cmd)),cwd=cwd,env=env,check=True)
def annotate_phase(path):
    replace(path,'barrier_t barrier, barrier_global;', '#include "phase_gate.h"\nbarrier_t barrier, barrier_global, hl_ready, hl_done, hl_release;')
    replace(path,'  barrier_cross(&barrier_global);\n\n  RR_START_SIMPLE();',
        '  barrier_cross(&hl_ready);\n  barrier_cross(&barrier_global);\n  hl_worker_phase(1);\n\n  RR_START_SIMPLE();')
    replace(path,'      TEST_LOOP(NULL);\n    }\n\n  barrier_cross(&barrier);',
        '      TEST_LOOP(NULL);\n    }\n\n  hl_worker_phase(2);\n  barrier_cross(&hl_done);\n  barrier_cross(&hl_release);\n  barrier_cross(&barrier);')
    replace(path,'  barrier_init(&barrier_global, num_threads + 1);',
        '  barrier_init(&barrier_global, num_threads + 1);\n  barrier_init(&hl_ready, num_threads + 1);\n  barrier_init(&hl_done, num_threads + 1);\n  barrier_init(&hl_release, num_threads + 1);\n  hl_gate_init();')
    replace(path,'  barrier_cross(&barrier_global);\n  gettimeofday(&start, NULL);',
        '  barrier_cross(&hl_ready);\n  hl_counter_gate(1);\n  barrier_cross(&barrier_global);\n  gettimeofday(&start, NULL);')
    replace(path,'  gettimeofday(&end, NULL);',
        '  gettimeofday(&end, NULL);\n  barrier_cross(&hl_done);\n  hl_counter_gate(0);\n  barrier_cross(&hl_release);')
def prepare_logger():
    logger=BUILD/'wait-memhook';shutil.copytree(ROOT/'memhook',logger,ignore=shutil.ignore_patterns('*.o','*.so'))
    shutil.copy2(CONTROL/'overhead-wait-probe.h',logger/'overhead-wait-probe.h')
    p=logger/'memhook.h'
    for old,new in [
      ('int global_fd;','int global_fd;\n#include "overhead-wait-probe.h"'),
      ('aio_suspend(async_api_struct_list, 1, NULL) != 0) {\n              cout','hl_wait(async_api_struct_list, 1, NULL, 1) != 0) {\n              cout'),
      ('aio_suspend(async_api_struct_list, 1, NULL) != 0) {\n        cout','hl_wait(async_api_struct_list, 1, NULL, 0) != 0) {\n        cout'),
      ('if (log_index == MEMHOOK_MAX_BUFFER_SIZE) {','if (log_index == MEMHOOK_MAX_BUFFER_SIZE) {\n    ++hl_full[hl_phase];'),
      ('mem_pool_obj.add(allocation_log[buffer_index], unfilled_buffer_size);','mem_pool_obj.add(allocation_log[buffer_index], unfilled_buffer_size);\n        hl_report();')]:replace(p,old,new)
    run(['make','MEMHOOK_ASCYLIB=1','-j4'],logger)
    return logger
def main():
    assert not (BUILD/'manifest.json').exists()
    logger=prepare_logger()
    ssmem=BUILD/'ssmem';ssmem.mkdir()
    run(['gcc','-shared','-fPIC','-O3','-D_GNU_SOURCE','-Iartifact/vendor/ssmem/include',
        'artifact/vendor/ssmem/src/ssmem.c','-o',ssmem/'libssmem_x86_64.so','-lpthread','-lrt'])
    records=[]
    for name,spec in SPECS.items():
      for variant in ['before','after']:
        base=BUILD/f'{name}-{variant}-plain';inst=BUILD/f'{name}-{variant}-logging'
        shutil.copytree(ROOT/'artifact/vendor/ascylib',base)
        run(['bash','-c','source artifact/lib/prepare_ascylib.sh; prepare_ascylib /root/sifter '+str(base)])
        run(['patch','--batch','-d',base,'-p1','-i',ROOT/'artifact/patches/ascylib-clang14.patch'])
        flags=spec['flags']+(spec['optimized'] if variant=='after' else [])
        ld=f'-no-pie -L{ssmem} -Wl,-rpath={ssmem}'
        # Instrument before adding the measurement-only markers.
        run(['./sifter.sh',base,inst,'-s','src/'+spec['tree'],'--skip-refactor','--build',
            f"env CFLAGS=-fno-pie LDFLAGS='{ld}' bear -- make "+' '.join(flags)])
        run(['clang-apply-replacements-14','./'],inst)
        run(['./sifter.sh',inst,'--includes-only'])
        for arm,src in [('plain',base),('logging',inst)]:
            sub=src/'src'/spec['tree']
            shutil.copy2(CONTROL/'phase_gate.h',sub/'phase_gate.h')
            annotate_phase(sub/'test_simple.c')
            env=dict(os.environ,CFLAGS='-fno-pie',LDFLAGS=ld)
            if arm=='logging':
                env['CFLAGS']+=f' -DMEMHOOK_ASCYLIB -I{logger}'
                env['LDFLAGS']+=f' -L{logger} -Wl,-rpath={logger} -lmemhook -ldl'
            run(['make','clean',*flags],sub,env)
            run(['make',*flags],sub,env)
            binary=src/'bin'/spec['binary']
            libs=subprocess.check_output(['ldd',str(binary)],text=True)
            assert str(ssmem/'libssmem_x86_64.so') in libs,libs
            if arm=='logging':assert str(logger/'libmemhook.so') in libs,libs
            (sub/'linkage.txt').write_text(libs)
            if arm=='logging':
                assert (sub/'typeset_dump.txt').stat().st_size>0
                assert (sub/'fileset_dump.txt').stat().st_size>0
            records.append(dict(application=name,variant=variant,arm=arm,**spec,
                flags_effective=flags,path=str(binary),sha256=sha(binary),cwd=str(sub)))
    manifest=dict(records=records,logger_sha256=sha(logger/'libmemhook.so'),
        ssmem_sha256=sha(ssmem/'libssmem_x86_64.so'),
        scope='Headline configurations; both arms use dynamically linked identical SSMEM and identical phase gates.')
    (BUILD/'manifest.json').write_text(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
