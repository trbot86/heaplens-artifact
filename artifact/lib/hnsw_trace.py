"""Port retained semantic-region annotations onto the performance source snapshot.

This is a diagnostic workload, not an instrumented throughput result. The
allocation/layout implementation and huge-page advice stay unchanged.
"""
import os
import shutil
from lib.valkey_trace import prepare_toolchain,replace_once


def annotate(work):
    header=work/'hnswlib/hnswalg.h'
    replace_once(header,'#include "visited_list_pool.h"','#include "visited_list_pool.h"\n#include "heaplens_hooks.h"')
    bridge='''
inline int heaplens_hnsw_layout_variant() {
#ifdef HNSWLIB_LAYOUT_VECTOR_SOA64
    return 1;
#else
    return 0;
#endif
}
inline const char* heaplens_hnsw_layout_variant_name() { return heaplens_hnsw_layout_variant() ? "separate-aligned-vectors-hugepage-advice" : "packed"; }
'''
    replace_once(header,'namespace hnswlib {','namespace hnswlib {\n'+bridge)
    replace_once(header,'            throw std::runtime_error("Not enough memory");\n\n#ifdef HNSWLIB_LAYOUT_VECTOR_SOA64',
        '            throw std::runtime_error("Not enough memory");\n        HEAPLENS_LOG_REGION(HeapLensHnswLevel0Slab,data_level0_memory_,elements * size_data_per_element_,heaplens::kFileHnswAlg);\n\n#ifdef HNSWLIB_LAYOUT_VECTOR_SOA64')
    replace_once(header,'        memset(data_memory_, 0, elements * data_memory_stride_);',
        '        memset(data_memory_, 0, elements * data_memory_stride_);\n        HEAPLENS_LOG_REGION(HeapLensHnswVectorSlab,data_memory_,elements * data_memory_stride_,heaplens::kFileHnswAlg);')
    anchor='        memcpy(getDataByInternalId(cur_c), data_point, data_size_);'
    regions='''
        char* region = data_level0_memory_ + cur_c * size_data_per_element_;
        HEAPLENS_LOG_REGION(HeapLensHnswLevel0Element,region,size_data_per_element_,heaplens::kFileHnswAlg);
        HEAPLENS_LOG_REGION(HeapLensHnswLevel0LinkCount,region+offsetLevel0_,sizeof(linklistsizeint),heaplens::kFileHnswAlg);
        HEAPLENS_LOG_REGION(HeapLensHnswLevel0Neighbors,region+offsetLevel0_+sizeof(linklistsizeint),size_links_level0_-sizeof(linklistsizeint),heaplens::kFileHnswAlg);
        HEAPLENS_LOG_REGION(HeapLensHnswVectorPayload,getDataByInternalId(cur_c),data_size_,heaplens::kFileHnswAlg);
        HEAPLENS_LOG_REGION(HeapLensHnswLabel,getExternalLabeLp(cur_c),sizeof(labeltype),heaplens::kFileHnswAlg);
'''
    replace_once(header,anchor,anchor+regions)
    anchor='            memset(linkLists_[cur_c], 0, upperLinkAllocationSize(linkListSize));'
    replace_once(header,anchor,anchor+'''
            HEAPLENS_LOG_REGION(HeapLensHnswUpperLinksBlock,linkLists_[cur_c],upperLinkAllocationSize(linkListSize),heaplens::kFileHnswAlg);
            for(int level=0;level<curlevel;++level) {
                char* upper=linkLists_[cur_c]+level*size_links_per_element_+upperLinkHeaderOffset();
                HEAPLENS_LOG_REGION(HeapLensHnswUpperLinkCount,upper,sizeof(linklistsizeint),heaplens::kFileHnswAlg);
                HEAPLENS_LOG_REGION(HeapLensHnswUpperNeighbors,upper+sizeof(linklistsizeint),maxM_*sizeof(tableint),heaplens::kFileHnswAlg);
            }
''')


def execute(args,out,api):
    tool=prepare_toolchain(api.ROOT,out)
    api.run(['make','USE_TEMPLATE=1','-j'+str(args.jobs)],cwd=tool/'memhook',log=out/'logger-build.log')
    work=out/'source';shutil.copytree(api.VENDOR/'hnswlib-corrected',work,ignore=api.IGNORE)
    assets=api.ART/'lib/hnsw_trace'
    shutil.copy2(assets/'heaplens_hooks.h',work/'hnswlib/heaplens_hooks.h')
    hooks=work/'hnswlib/heaplens_hooks.h'
    replace_once(hooks,'#include "memhook_interface.h"','#include "memhook_interface.h"\nextern "C" void memhook_record_alloc(void*,size_t,int,uint16_t,uint16_t);\n#define MEMHOOK_LOG_CPP_ALLOC_AT(ptr, sz, tid, fid, ln) memhook_record_alloc(ptr,sz,ln,fid,typetable.insert(&tid));')
    shutil.copy2(assets/'heaplens_hnsw_bench.cpp',work/'trace.cpp')
    annotate(work)
    optimized=args.variant=='optimized'
    defines=['-DHNSWLIB_LAYOUT_VECTOR_SOA64=1','-DHNSWLIB_LAYOUT_MADVISE_HUGEPAGE=1'] if optimized else []
    binary=work/'trace'
    api.run(['g++','-O3','-std=c++17','-pthread','-DHEAPLENS_ENABLE',*defines,'-I'+str(work),'-I'+str(tool/'memhook'),
        str(work/'trace.cpp'),'-L'+str(tool/'memhook'),'-Wl,-rpath='+str(tool/'memhook'),'-lmemhook','-ldl','-o',binary],log=out/'build.log')
    dims=[args.dim] if args.dim else ([128,1536] if args.profile=='paper' else [128])
    for dim in dims:
        trial=out/f'd{dim}';trial.mkdir()
        count=1000000 if args.profile=='paper' else 2000
        threads=args.threads or (24 if args.profile=='paper' else 2)
        cmd=[str(binary),'--elements',str(count),'--dim',str(dim),'--queries','1000','--iterations','1','--warmup','100',
             '--threads',str(threads),'--build-threads',str(threads),'--m','16','--ef-construction','200','--ef-search','64','--k','10','--query-mode','indexed','--seed','47']
        api.save(trial/'protocol.json',dict(command=cmd,defines=defines,source='hnswlib-corrected',
            scope='Retained C++ diagnostic workload with semantic slab/element/vector/link/label regions; not throughput reproduction'))
        env=dict(os.environ,MEMHOOK_OUTPUT_DUMP_FILE=str(trial/'binary_dump.txt'),MEMHOOK_OUTPUT_TYPE_FILE=str(trial/'typeset_dump.txt'))
        api.run(cmd,cwd=trial,env=env,log=trial/'benchmark.log',timeout=3600)
        (trial/'fileset_dump.txt').write_text('65001|hnswlib/hnswalg.h\n65002|hnswlib/visited_list_pool.h\n65003|trace.cpp\n')
        api.run([tool/'sifter.sh',trial,'-d','--sample','0.1','--pages-per-type','1','--use-container'],cwd=tool,log=trial/'convert.log')
        db=trial/'hnsw.sqlite';shutil.copy2(tool/'type_analysis/allocs.sqlite',db)
        api.run(['python3',api.ART/'check_database.py',db],log=trial/'database-check.log')
