"""Private source-matched Python binding builds only; no workload execution."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from hnsw_phase_overlay import benchmark,bindings
from hnsw_logger_overlay import transform as logger_overlay
from valkey_terminal_overlay import replace_once
import hnsw_query_overlay

ROOT=Path('/root/sifter'); CONTROL=Path('/control/drivers'); BUILD=Path('/build')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    sys.path.insert(0,str(ROOT/'artifact'))
    from lib import hnsw_trace as trace
    source=ROOT/'artifact/vendor/hnswlib-corrected'
    expected={'python_bindings/bindings.cpp':'bd58fb5a0586c26d784965fdc3975e3f17f431e23a6417fc135965073fdf9131',
              'benchmark.py':'842b7189008f17d6995becce73f4f24f870fc0646809464af697ff922b2f16ab'}
    for name,digest in expected.items():
        if sha(source/name)!=digest: raise ValueError('frozen HNSW source mismatch: '+name)
    for variant in ('baseline','optimized'):
      for arm in ('plain','logging'):
        out=BUILD/(variant+'-'+arm); out.mkdir()
        work=out/'source'
        shutil.copytree(source,work,ignore=shutil.ignore_patterns('.git','build','*.so','*.o','__pycache__'))
        manifest=dict(status='preparing',variant=variant,arm=arm,allocator='system libc',source_sha256=expected,
                      source_revision='7f4f5f20125ad0a2571abc8ddb0e98e13c7ae109',binaries={})
        def save(): (out/'preparation.json').write_text(json.dumps(manifest,indent=2)+'\n')
        save()
        defines=[] if variant=='baseline' else ['HNSWLIB_LAYOUT_VECTOR_SOA64=1','HNSWLIB_LAYOUT_MADVISE_HUGEPAGE=1']
        env=os.environ.copy()
        for key in ('LD_PRELOAD','PYTHONPATH','HNSWLIB_NO_NATIVE','CFLAGS','CXXFLAGS','LDFLAGS','GLIBC_TUNABLES'):
            env.pop(key,None)
        if arm=='logging':
            tool=trace.prepare_toolchain(ROOT,out); logger=tool/'memhook'
            for name in ('aio_completion.h','overhead-wait-probe.h'): shutil.copy2(CONTROL/name,logger/name)
            (logger/'memhook.h').write_text(logger_overlay((logger/'memhook.h').read_text()))
            cpp=logger/'memhook.cpp'; cpp.write_text(hnsw_query_overlay.logger(cpp.read_text()))
            with (out/'logger-build.log').open('x') as log:
                subprocess.run(['make','USE_TEMPLATE=1','-j4'],cwd=logger,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
            hooks=work/'hnswlib/heaplens_hooks.h'
            shutil.copy2(ROOT/'artifact/lib/hnsw_trace/heaplens_hooks.h',hooks)
            hooks.write_text(replace_once(hooks.read_text(),'#include "memhook_interface.h"',
                '#include "memhook_interface.h"\nextern "C" void memhook_record_alloc(void*,size_t,int,uint16_t,uint16_t);\n#define MEMHOOK_LOG_CPP_ALLOC_AT(ptr, sz, tid, fid, ln) memhook_record_alloc(ptr,sz,ln,fid,typetable.insert(&tid));'))
            trace.annotate(work)
            hooks.write_text(hnsw_query_overlay.hooks(hooks.read_text()))
            alg=work/'hnswlib/hnswalg.h'; alg.write_text(hnsw_query_overlay.algorithm(alg.read_text()))
            visited=work/'hnswlib/visited_list_pool.h'
            text=replace_once(visited.read_text(),'#include <deque>','#include <deque>\n#include "heaplens_hooks.h"')
            text=replace_once(text,'        mass = new vl_type[numelements];',
                '        mass = new vl_type[numelements];\n        HEAPLENS_LOG_REGION(HeapLensHnswVisitedList,this,sizeof(*this),heaplens::kFileVisitedListPool);\n        HEAPLENS_LOG_REGION(HeapLensHnswVisitedMass,mass,sizeof(vl_type)*numelements,heaplens::kFileVisitedListPool);')
            visited.write_text(text)
            defines+=['HEAPLENS_ENABLE=1']
            # setup.py's custom compiler path ignores environment CFLAGS here.
            setup=work/'setup.py'
            setup_text=replace_once(setup.read_text(),'libraries = []',
                'include_dirs.append('+repr(str(logger))+')\nlibraries = ["memhook", "dl"]')
            setup_text=replace_once(setup_text,'        extra_objects=extra_objects,',
                '        extra_objects=extra_objects,\n        library_dirs=['+repr(str(logger))+'],\n        runtime_library_dirs=['+repr(str(logger))+'],')
            setup.write_text(setup_text)
            manifest['binaries'][str(logger/'libmemhook.so')]=sha(logger/'libmemhook.so')
        shutil.copy2(CONTROL/'hnsw_phase.h',work/'python_bindings/hnsw_phase.h')
        shutil.copy2(CONTROL/'valkey_protocol.py',work/'valkey_protocol.py')
        shutil.copy2(CONTROL/'portable_runtime.py',work/'portable_runtime.py')
        (work/'benchmark.py').write_text(benchmark((work/'benchmark.py').read_text()))
        binding=work/'python_bindings/bindings.cpp'; binding.write_text(bindings(binding.read_text()))
        env.update(HNSWLIB_BENCH_CXX_DEFINES=' '.join(defines),OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1')
        with (out/'build.log').open('x') as log:
            subprocess.run([sys.executable,'setup.py','build_ext','--inplace','--force'],cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
        modules=list(work.glob('hnswlib*.so'))
        if len(modules)!=1: raise RuntimeError('module count')
        manifest['binaries'][str(modules[0])]=sha(modules[0])
        manifest.update(status='built_native_validation_pending',defines=defines,
                        benchmark_sha256=sha(work/'benchmark.py'),binding_sha256=sha(binding))
        save()

if __name__=='__main__': main()
