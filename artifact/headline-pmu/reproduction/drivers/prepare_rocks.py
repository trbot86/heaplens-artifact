"""Build a historical RocksDB pair; no workload is executed by this script."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import argparse,json,os,shlex,shutil
from pathlib import Path
from prepare_ascylib import ROOT,BUILD,CONTROL,run,replace,sha

def annotate(src):
    p=src/'tools/db_bench_tool.cc'
    shutil.copy2(CONTROL/'phase_gate.h',p.parent/'phase_gate.h')
    replace(p,'int db_bench_tool(int argc, char** argv) {','int db_bench_tool(int argc, char** argv) {\n  hl_gate_init();')
    replace(p,'#include <cstdio>','#include "phase_gate.h"\n#include <cstdio>')
    replace(p,'  bool start;','  bool start;\n  bool hl_measured = false;')
    replace(p,'    shared.total = n;','    shared.total = n;\n    shared.hl_measured = name.ToString() == "readwhilewriting";')
    replace(p,'    shared.start = true;','    if (shared.hl_measured) hl_counter_gate(1);\n    shared.start = true;')
    replace(p,'    // Stats for some threads can be excluded.','    if (shared.hl_measured) hl_counter_gate(0);\n\n    // Stats for some threads can be excluded.')
    replace(p,'    (arg->bm->*(arg->method))(thread);','    if (shared->hl_measured) hl_worker_phase(1);\n    (arg->bm->*(arg->method))(thread);\n    if (shared->hl_measured) hl_worker_phase(2);')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--app',choices=['hsl','isl'],required=True)
    parser.add_argument('--variant',choices=['before','after'],required=True);args=parser.parse_args()
    logger=BUILD/'wait-memhook'
    if not logger.exists():shutil.copytree('/previous-logger',logger)
    run(['make','clean'],ROOT/'memhook')
    base=BUILD/f'{args.app}-{args.variant}-plain';inst=BUILD/f'{args.app}-{args.variant}-logging'
    shutil.copytree(ROOT/'artifact/vendor/rocksdb-historical',base,ignore=shutil.ignore_patterns('.git','*.o','*.a','*.so','db_bench'))
    run(['patch','--batch','-p1','-i',ROOT/'artifact/patches/rocksdb-historical.patch'],base)
    flags=['PORTABLE=1','DEBUG_LEVEL=0','DISABLE_WARNING_AS_ERROR=1','USE_RTTI=1']
    if args.variant=='after':flags+=['REORDER_FIELDS=1'] if args.app=='hsl' else ['ALIGN_TALL_NODE=3','SEG_TALL_NODE=3']
    run(['./sifter.sh',base,inst,'-t','--skip-refactor','--build',shlex.join(['bear','--','make',*flags,'db_bench','-j4'])])
    lib=ROOT/'artifact/lib'
    run(['python3',lib/'dedupe_fixes_yaml.py',inst/'fixes.yaml'])
    run(['clang-apply-replacements-14','./'],inst)
    for script in ['fixup_anon_namespace_casts.py','fixup_malformed_insertions.py']:run(['python3',lib/script,inst])
    run(['./sifter.sh',inst,'--includes-only'])
    run(['python3',lib/'patch_allocate_overloads.py',inst])
    if args.app=='isl':run(['python3',lib/'rocksdb_inline_regions.py',inst])
    rows=[]
    for arm,src in [('plain',base),('logging',inst)]:
        annotate(src);run(['make','clean'],src)
        env=os.environ.copy()
        if arm=='logging':env.update(CXXFLAGS=f'-I{logger}',LDFLAGS=f'-L{logger} -Wl,-rpath={logger} -lmemhook -ldl')
        run(['make',*flags,'db_bench','-j4'],src,env)
        rows.append(dict(application=args.app,variant=args.variant,arm=arm,path=str(src/'db_bench'),
            sha256=sha(src/'db_bench'),cwd=str(src),flags=flags,source_phase_sha256=sha(src/'tools/db_bench_tool.cc')))
    target=BUILD/f'manifest-{args.app}-{args.variant}.json';assert not target.exists()
    target.write_text(json.dumps(dict(records=rows,logger_sha256=sha(logger/'libmemhook.so'),
        caveat='Both arms enable RTTI for typed instrumentation. Only benchmark-worker wait phases are delimited; background workers remain phase 0.'),indent=2))
if __name__=='__main__':main()
