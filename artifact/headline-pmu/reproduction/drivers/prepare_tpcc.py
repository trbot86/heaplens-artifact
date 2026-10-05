"""Source-matched TPC-C headline builds. Run only while no timings are active."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import json
import os
from pathlib import Path
import shutil
from prepare_ascylib import run,replace,sha,BUILD,ROOT,CONTROL

SPECS={
 'bcco':dict(ds='bronson_pext_bst_occ',allocator='libjemalloc.so',before='',
             after='-DMEMHOOK_SEG_DS -DMACROBENCH_PACK_LOCK'),
 'efrb':dict(ds='ellen_ext_bst_lf',allocator='libmimalloc.so',
             before='-DDEBRA_ORIGINAL_FREE -DMEMHOOK_SEG_DS',
             after='-DDEBRA_ORIGINAL_FREE -DMEMHOOK_SEG_DS -DMACROBENCH_PAD_ROW_TO_ALIGN -DMACROBENCH_SINGLE_RECMGR -DBST_ELLEN')}

def annotate(src):
    p=src/'system/main.cpp'
    shutil.copy2(CONTROL/'phase_gate.h',p.parent/'phase_gate.h')
    replace(p,'using namespace std;','#include "phase_gate.h"\nusing namespace std;')
    replace(p,'\tparser(argc, argv);','\tparser(argc, argv);\n        hl_gate_init();')
    replace(p,'\tint64_t starttime = get_server_clock();','        hl_counter_gate(1);\n\tint64_t starttime = get_server_clock();')
    replace(p,'\tint64_t endtime = get_server_clock();','\tint64_t endtime = get_server_clock();\n        hl_counter_gate(0);')
    # Limit the replacement to the measured entry point, excluding warmup.
    text=p.read_text();marker='void * f_real(void * id) {'
    assert text.count(marker)==1
    prefix,real=text.split(marker)
    old='\tm_thds[__tid]->run();'
    assert real.count(old)==1
    real=real.replace(old,'        hl_worker_phase(1);\n'+old+'\n        hl_worker_phase(2);')
    p.write_text(prefix+marker+real)

def main():
    assert not (BUILD/'manifest.json').exists()
    logger=BUILD/'wait-memhook';shutil.copytree(ROOT/'memhook',logger,ignore=shutil.ignore_patterns('*.o','*.so'))
    shutil.copy2(CONTROL/'overhead-wait-probe.h',logger/'overhead-wait-probe.h')
    p=logger/'memhook.h'
    for a,b in [
        ('int global_fd;','int global_fd;\n#include "overhead-wait-probe.h"'),
        ('aio_suspend(async_api_struct_list, 1, NULL) != 0) {\n              cout','hl_wait(async_api_struct_list, 1, NULL, 1) != 0) {\n              cout'),
        ('aio_suspend(async_api_struct_list, 1, NULL) != 0) {\n        cout','hl_wait(async_api_struct_list, 1, NULL, 0) != 0) {\n        cout'),
        ('if (log_index == MEMHOOK_MAX_BUFFER_SIZE) {','if (log_index == MEMHOOK_MAX_BUFFER_SIZE) {\n    ++hl_full[hl_phase];'),
        ('mem_pool_obj.add(allocation_log[buffer_index], unfilled_buffer_size);','mem_pool_obj.add(allocation_log[buffer_index], unfilled_buffer_size);\n        hl_report();')]:replace(p,a,b)
    run(['make','USE_TEMPLATE=1','-j4'],logger)
    # Force the sifter toolchain's separate, ordinary logger to use C++ templates.
    run(['make','clean'],ROOT/'memhook')
    records=[]
    for name,spec in SPECS.items():
      for variant in ['before','after']:
        base=BUILD/f'{name}-{variant}-plain';inst=BUILD/f'{name}-{variant}-logging'
        shutil.copytree(ROOT/'artifact/vendor/setbench',base)
        shutil.copytree(ROOT/'artifact/patches/setbench-tpcc',base,dirs_exist_ok=True)
        run(['bash','-c','source artifact/lib/tpcc_allocators.sh; tpcc_stage_allocators /root/sifter '+str(base)])
        flags=['THREAD_CNT=24','workload=TPCC','data_structure_name='+spec['ds'],'data_structure_opts='+spec[variant]]
        import shlex
        run(['./sifter.sh',base,inst,'-t','-s','macrobench','--skip-refactor','--build',
             'bear -- '+shlex.join(['make',*flags])])
        run(['clang-apply-replacements-14','./'],inst)
        run(['./sifter.sh',inst,'--includes-only'])
        for arm,src in [('plain',base),('logging',inst)]:
            sub=src/'macrobench';(sub/'bin').mkdir(exist_ok=True);annotate(sub)
            run(['make','clean',*flags],sub)
            extra=[]
            if arm=='logging':extra=[f'xargs=-DTHREAD_CNT=24 -I{logger} -L{logger} -Wl,-rpath={logger} -lmemhook -ldl']
            run(['make','-j4',*flags,*extra],sub)
            binary=sub/'bin'/('rundb_TPCC_'+spec['ds'])
            allocator=src/'lib'/spec['allocator']
            records.append(dict(application=name,variant=variant,arm=arm,path=str(binary),sha256=sha(binary),
                cwd=str(sub),threads=24,allocator=str(allocator),allocator_sha256=sha(allocator),flags=flags,
                config_sha256=sha(sub/'config.h')))
    (BUILD/'manifest.json').write_text(json.dumps(dict(records=records,logger_sha256=sha(logger/'libmemhook.so'),
        scope='Final TPC-C headline configurations, phase-gated before measured thread creation and after joins.'),indent=2))
if __name__=='__main__':main()
