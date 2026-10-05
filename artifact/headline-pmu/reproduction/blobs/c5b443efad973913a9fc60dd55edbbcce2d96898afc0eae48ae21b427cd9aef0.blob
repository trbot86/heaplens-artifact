"""Typed Valkey preload traces using the retained semantic-allocation integration.

Instrumentation is built in a private toolchain. Neither the packaged logger
nor other experiments' clang matcher is modified. Optimized wrappers call the
optimized allocators, rather than aliasing them back to the baseline allocator.
"""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from lib import valkey_trace_support as support


def replace_once(path, old, new):
    text=path.read_text()
    if text.count(old)!=1: raise RuntimeError(f'Unexpected source at {path}: {old[:70]}')
    path.write_text(text.replace(old,new))


def prepare_toolchain(root, out):
    tool=out/'toolchain';tool.mkdir()
    ignore=shutil.ignore_patterns('build*','bin','*.o','*.so','*.sqlite','binary_dump.txt','__pycache__')
    for name in ('clang-tidy-standalone','memhook','type_analysis'):
        shutil.copytree(root/name,tool/name,ignore=ignore)
    (tool/'type_analysis/bin').mkdir(exist_ok=True)
    header=tool/'clang-tidy-standalone/misc/AllocationLoggingCheck.h'
    header.write_text(header.read_text().replace('/root/sifter',str(tool)))
    for name in ('sifter.sh','llvm.sh'):
        shutil.copy2(root/name,tool/name)
        p=tool/name;p.write_text(p.read_text().replace('/root/sifter',str(tool)));p.chmod(0o755)
    checker=tool/'clang-tidy-standalone/misc/AllocationLoggingCheck.cpp'
    names=sorted(n for n in support.SEMANTIC_ALLOCATOR_SOURCE_NAMES if not n.startswith(('s_','lp_','rax_')))
    names+=['rax_segregated_malloc','rax_segregated_realloc','zmallocRobjUsable']
    extra=''.join(f'hasName("{n}"), ' for n in names)
    replace_once(checker,'hasName("_mm_malloc"),',extra+'hasName("_mm_malloc"),')
    hooks='''
extern "C" void memhook_record_alloc(void* ptr, size_t size, int line, uint16_t fid, uint16_t tid) {
    if (!ptr || !initialized) return;
    if (!setup) { exiter.add(); setup=true; }
    unit_log.timestamp=memhook_get_server_clock(); unit_log.size=size;
    unit_log.addr=ptr; unit_log.typeofop=true; unit_log.line=line;
    unit_log.file=fid; unit_log.tindex_name=tid; memhookCollector.copy(unit_log);
}
extern "C" void memhook_record_free(void* ptr) {
    if (!ptr || !initialized) return;
    if (!setup) { exiter.add(); setup=true; }
    unit_log.timestamp=memhook_get_server_clock(); unit_log.size=0;
    unit_log.addr=ptr; unit_log.typeofop=false; memhookCollector.copy(unit_log);
}
'''
    p=tool/'memhook/memhook.cpp';p.write_text(p.read_text()+hooks)
    support.CONTAINER_SIFTER_ROOT=tool
    support.MEMHOOK_CFLAGS=support.MEMHOOK_CFLAGS.replace('/root/sifter',str(tool))
    support.MEMHOOK_LIBS=support.MEMHOOK_LIBS.replace('/root/sifter',str(tool))
    support.SEMANTIC_ALLOCATOR_SOURCE_NAMES |= {'zmallocRobjUsable','rax_segregated_malloc','rax_segregated_realloc'}
    return tool


def preserve_allocator_semantics(work, optimized):
    # Jemalloc's sdallocx is not intercepted by the generic free() hook.
    path=work/'src/zmalloc.c'
    for signature in ('void zfree(void *ptr) {','void zfree_with_size(void *ptr, size_t size) {'):
        replace_once(path,signature,signature+'\n    memhook_record_free(ptr);')
    if not optimized:return
    rax=work/'src/rax_malloc.h'
    replace_once(rax,'#define rax_malloc_s zmalloc_s', '''static inline void *rax_malloc_s(size_t size, int line, uint16_t fid, uint16_t tid) {
    return heaplens_valkey_record_alloc(rax_segregated_malloc(size), size, line, fid, tid);
}''')
    replace_once(rax,'#define rax_realloc_s zrealloc_s', '''static inline void *rax_realloc_s(void *ptr, size_t size, int line, uint16_t fid, uint16_t tid) {
    void *result=rax_segregated_realloc(ptr,size);
    return heaplens_valkey_record_realloc(ptr,result,size,line,fid,tid);
}''')
    # Macro expansion may cause the checker to use the underlying function name.
    with rax.open('a') as f:f.write('\n#define rax_segregated_malloc_s rax_malloc_s\n#define rax_segregated_realloc_s rax_realloc_s\n')
    obj=work/'src/object.c'
    marker='/* Creates an object, optionally with embedded key and expire fields.'
    wrapper='''static inline robj *zmallocRobjUsable_s(size_t size, size_t *usable, int line, uint16_t fid, uint16_t tid) {
    robj *ptr=zmallocRobjUsable(size,usable);
    return (robj*)heaplens_valkey_record_alloc(ptr,heaplens_valkey_record_size(size,usable),line,fid,tid);
}

'''
    replace_once(obj,marker,wrapper+marker)


def execute(args,out,api):
    variant=args.variant or 'baseline';optimized=variant=='optimized'
    tool=prepare_toolchain(api.ROOT,out)
    source=out/'source';shutil.copytree(api.VENDOR/'valkey',source,ignore=api.IGNORE)
    if optimized:api.run(['patch','--batch','-p1','-i',api.ART/'patches/valkey-B1C1_64.patch'],cwd=source,log=out/'patch.log')
    work=out/'instrumented'
    support.instrument_valkey(source,work,out,str(args.jobs),'jemalloc')
    preserve_allocator_semantics(work,optimized)
    support.build_instrumented_valkey(work,out/'build.log',str(args.jobs),'jemalloc')
    trial=out/'trace';trial.mkdir()
    keys=1000000 if args.profile=='paper' else 2000
    api.save(out/'protocol.json',dict(variant=variant,allocator='jemalloc',keys=keys,value_bytes=128,
             scope='Instrumented preload for visualization; not a throughput comparison'))
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    command=[str(work/'src/valkey-server'),'--bind','127.0.0.1','--port',str(port),'--save','','--appendonly','no','--daemonize','no','--dir',str(trial)]
    env=dict(os.environ,LD_PRELOAD=str(tool/'memhook/libmemhook.so'),MEMHOOK_OUTPUT_DUMP_FILE=str(trial/'binary_dump.txt'))
    with (trial/'server.log').open('w') as log:
        proc=subprocess.Popen(command,env=env,cwd=trial,stdout=log,stderr=subprocess.STDOUT)
        try:
            for _ in range(200):
                if proc.poll() is not None:raise RuntimeError('Valkey exited; inspect trace/server.log')
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.2) as client:
                        client.sendall(b'PING\r\n')
                        if client.recv(100).startswith(b'+PONG'):break
                except OSError:pass
                time.sleep(.1)
            else:raise RuntimeError('Valkey startup timeout')
            # Sequential RESP preload, bounded batches; keep values identical.
            with socket.create_connection(('127.0.0.1',port),timeout=120) as client:
                reader=client.makefile('rb')
                for start in range(1,keys+1,256):
                    batch=[]
                    for key in range(start,min(keys+1,start+256)):
                        name=f'heaplens:{key}'.encode();value=b'x'*128
                        batch.append(b'*3\r\n$3\r\nSET\r\n$'+str(len(name)).encode()+b'\r\n'+name+b'\r\n$128\r\n'+value+b'\r\n')
                    client.sendall(b''.join(batch))
                    for _ in batch:
                        if reader.readline()!=b'+OK\r\n':raise RuntimeError('Preload failed')
            api.run([work/'src/valkey-cli','-p',str(port),'shutdown','nosave'],log=trial/'shutdown.log')
            if proc.wait(timeout=120)!=0:raise RuntimeError('Valkey shutdown failed')
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=30)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
    for name in ('typeset_dump.txt','fileset_dump.txt','fielddump.txt'):
        shutil.copy2(work/name,trial/name)
    api.run([tool/'sifter.sh',trial,'-d','--sample','0.2','--pages-per-type','1','--field-dump','fielddump.txt'],cwd=tool,log=out/'convert.log')
    db=out/'valkey.sqlite';shutil.copy2(tool/'type_analysis/allocs.sqlite',db)
    api.run(['python3',api.ART/'check_database.py',db],log=out/'database-check.log')
