"""Regression checks for evaluator-requested output/trace/overhead workflows."""
from contextlib import redirect_stderr
import gzip
import json
import io
from pathlib import Path
import sys
import tempfile
import unittest
import os
import subprocess
import sqlite3
import shutil
from argparse import Namespace
from unittest.mock import patch

ART=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ART))
import ae
from lib.overhead_campaign import archive_trace
from lib.overhead_campaign import execute as overhead_execute
from lib.rocksdb_trace_layout import apply
from lib.valkey_trace import preserve_allocator_semantics
from lib.valkey_trace_support import write_compile_commands_helper
from lib.rocksdb_inline_regions import apply as annotate_inline, verify as verify_inline


class Workflows(unittest.TestCase):
    def test_host_paths_only_translate_files_inside_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo'
            with patch.object(ae, 'ROOT', root), patch.dict(os.environ, HEAPLENS_HOST_ROOT='/host/project with spaces'):
                self.assertEqual(ae.host_path(root / 'artifact/results/example'),
                                 '/host/project with spaces/artifact/results/example')
                outside = Path(tmp) / 'repo-other/result'
                self.assertEqual(ae.host_path(outside), str(outside))
            with patch.dict(os.environ, HEAPLENS_HOST_ROOT=''):
                self.assertEqual(ae.host_path(root / 'artifact/results/example'),
                                 str(root / 'artifact/results/example'))

    def test_efrb_trace_build_flags_isolate_each_change(self):
        # Execute the driver's selection before it performs builds or writes.
        source = (ART/'lib/ascylib_experiment.sh').read_text()
        body = source[source.index('    local tree_src_dir='):source.index('    local SIFTER_ROOT')]
        script = 'select_flags() {\n' + body + '\nprintf "%s\\n" "${make_args[@]}"\n}\nselect_flags src/bst-ellen lf-bst_ellen "$TEST_NAME" STM=LOCKFREE'
        expected = {'baseline': [], 'segregation-only': ['SEG_OBJS=1'],
                    'prefill-only': ['INIT=all'], 'optimized': ['SEG_OBJS=1', 'INIT=all']}
        for variant, flags in expected.items():
            result = subprocess.run(['bash', '-c', script], capture_output=True, text=True,
                env={**os.environ, 'TRACE_VARIANT': variant, 'TEST_NAME': 'ascylib_efrb'})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ['STM=LOCKFREE', 'SET_CPU=0'] + flags)
        for name, variant in [('ascylib_efrb', 'unknown'), ('ascylib_dvy', 'prefill-only'),
                              ('ascylib_hj', 'segregation-only')]:
            result = subprocess.run(['bash', '-c', script], capture_output=True, text=True,
                env={**os.environ, 'TRACE_VARIANT': variant, 'TEST_NAME': name})
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')

    def test_hj_before_uses_jemalloc_and_after_uses_glibc(self):
        source = (ART/'lib/ascylib_experiment.sh').read_text()
        start = source.index('        local preload=')
        end = source.index('        LD_PRELOAD=', start)
        selection = source[start:end].replace('local preload=', 'preload=')
        for variant, expected in [('baseline', '/fixture/memhook/libmemhook.so:/fixture/artifact/vendor/heaplens-allocators/libjemalloc-heaplens.so'),
                                  ('optimized', '/fixture/memhook/libmemhook.so')]:
            result = subprocess.run(['bash', '-c', selection + '\n printf "%s" "$preload"'],
                env={**os.environ, 'out_name': 'ascylib_hj', 'variant': variant,
                     'MEMHOOK_DIR': '/fixture/memhook', 'SIFTER_ROOT': '/fixture'},
                check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout, expected)

    def test_inline_trace_requires_regions_and_optimized_alignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE SUPERTABLE(TYPE TEXT,ACTUALADDR INT,ACTUALSIZE INT,isNew INT)')
                db.execute("INSERT INTO SUPERTABLE VALUES('rocksdb::InlineSkipList<C>::Node',4120,40,1)")
            with self.assertRaises(RuntimeError):verify_inline(path)
            with sqlite3.connect(path) as db:
                db.execute("INSERT INTO SUPERTABLE VALUES('std::atomic<rocksdb::InlineSkipList<C>::Node*>',4096,24,1)")
            verify_inline(path,True)
            with sqlite3.connect(path) as db:
                db.execute("UPDATE SUPERTABLE SET ACTUALADDR=4112 WHERE TYPE LIKE 'std::atomic%'")
            verify_inline(path,False)
            with self.assertRaises(RuntimeError):verify_inline(path,True)

    def test_inline_regions_do_not_replace_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'memtable').mkdir()
            header=root/'memtable/inlineskiplist.h'
            allocation='  char* raw = allocator_->AllocateAligned(prefix + sizeof(Node) + key_size);\n'
            header.write_text(allocation+'  Node* x = reinterpret_cast<Node*>(raw + prefix);\n')
            (root/'fileset_dump.txt').write_text('7|other.h\n')
            annotate_inline(root)
            self.assertIn(allocation,header.read_text())
            self.assertIn('MEMHOOK_LOG_CPP_ALLOC(raw, prefix',header.read_text())
            self.assertIn('MEMHOOK_LOG_CPP_ALLOC(x, sizeof(Node) + key_size',header.read_text())
            self.assertIn('8|memtable/inlineskiplist.h',(root/'fileset_dump.txt').read_text())
            with self.assertRaises(RuntimeError):annotate_inline(root)

    def test_valkey_compile_filter_excludes_dependency_src(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'work').mkdir()
            helper=write_compile_commands_helper(root,'2','jemalloc')
            # Run the exact generated filter, without its build commands.
            script=helper.read_text().split("python3 - <<'PY'\n",1)[1].rsplit('\nPY',1)[0]
            entries=[{'directory':str(root),'file':str(root/'src/server.c')},
                     {'directory':str(root/'deps/jemalloc'),'file':'src/test_hooks.c'},
                     {'directory':str(root),'file':str(root/'src/zmalloc.c')},
                     {'directory':str(root),'file':str(root/'src/valkey-cli.c')}]
            (root/'compile_commands.json').write_text(json.dumps(entries))
            subprocess.run([sys.executable,'-c',script],cwd=root,check=True)
            self.assertEqual(json.loads((root/'compile_commands.json').read_text()),entries[:1])

    def test_valkey_wrappers_preserve_optimized_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'src';src.mkdir()
            (src/'zmalloc.c').write_text('void zfree(void *ptr) {\n}\nvoid zfree_with_size(void *ptr, size_t size) {\n}\n')
            (src/'rax_malloc.h').write_text('#define rax_malloc_s zmalloc_s\n#define rax_realloc_s zrealloc_s\n')
            (src/'object.c').write_text('/* Creates an object, optionally with embedded key and expire fields. */\n')
            preserve_allocator_semantics(root,True)
            rax=(src/'rax_malloc.h').read_text()
            self.assertIn('rax_segregated_malloc(size)',rax)
            self.assertIn('rax_segregated_realloc(ptr,size)',rax)
            self.assertNotIn('#define rax_malloc_s zmalloc_s',rax)
            self.assertIn('zmallocRobjUsable(size,usable)',(src/'object.c').read_text())
            self.assertEqual((src/'zmalloc.c').read_text().count('memhook_record_free(ptr)'),2)

    def test_conversion_preserves_trace_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'trace';source.mkdir()
            (root/'type_analysis/bin').mkdir(parents=True)
            shutil.copy2(ART.parent/'sifter.sh',root/'sifter.sh')
            raw=b'untouched original input'
            (source/'binary_dump.txt').write_bytes(raw)
            (source/'typeset_dump.txt').write_text('1|Node\n')
            (source/'fileset_dump.txt').write_text('1|test.cpp\n')
            converter=root/'type_analysis/bin/convert_to_db'
            converter.write_text('#!/bin/sh\nprintf corrupted > binary_dump.txt\nexit 23\n')
            converter.chmod(0o755)
            (root/'type_analysis/Makefile').write_text('bin/convert_to_db:\n\t@true\n')
            result=subprocess.run(['bash','sifter.sh',str(source),'-d'],cwd=root,capture_output=True)
            self.assertEqual(result.returncode,23)
            self.assertEqual((source/'binary_dump.txt').read_bytes(),raw)

    def test_gui_import_retains_distinct_runs_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'sifter_vis_d3').mkdir()
            before=root/'before'/'trace.sqlite';before.parent.mkdir()
            with sqlite3.connect(before) as db:
                db.execute('CREATE TABLE SUPERTABLE(ADDRESS INT, TYPE TEXT)')
                db.execute("INSERT INTO SUPERTABLE VALUES(4096,'Node')")
            args=Namespace(database=str(before),label=None)
            with patch.object(ae,'ROOT',root):
                target=ae.import_gui_database(args)
                self.assertEqual(target.name,'before-trace.sqlite')
                self.assertEqual(ae.import_gui_database(args),target)
                with sqlite3.connect(before) as db:
                    db.execute("INSERT INTO SUPERTABLE VALUES(8192,'Node')")
                with self.assertRaises(ValueError):ae.import_gui_database(args)
                args.label='after'
                other=ae.import_gui_database(args)
                self.assertNotEqual(target,other)
                with sqlite3.connect(target) as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM SUPERTABLE').fetchone()[0],1)
                args.label='../outside'
                with self.assertRaises(ValueError):ae.import_gui_database(args)

    def test_perf_kernel_guard_queries_daemon_and_does_not_escalate(self):
        with tempfile.TemporaryDirectory() as tmp:
            docker=Path(tmp)/'docker'
            docker.write_text('#!/bin/sh\nif [ "$1" = info ]; then echo "$TEST_KERNEL"; else printf "%s\\n" "$@" > "$TEST_DOCKER_LOG"; fi\n')
            docker.chmod(0o755)
            logfile=Path(tmp)/'calls'
            env=dict(os.environ,PATH=tmp+':'+os.environ['PATH'],HEAPLENS_PERF='1',
                     TEST_DOCKER_LOG=str(logfile))
            for kernel,expected in [('5.4.0',2),('5.8.0',0),('6.8.0',0)]:
                env['TEST_KERNEL']=kernel
                if logfile.exists():logfile.unlink()
                result=subprocess.run(['bash',str(ART/'run.sh'),'doctor'],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,expected,result.stderr)
                if expected:
                    self.assertFalse(logfile.exists())
                    self.assertIn('--cap-add SYS_ADMIN',result.stderr)
                    self.assertIn('broader privileges',result.stderr)
                else:
                    self.assertIn('PERFMON',logfile.read_text())
                    self.assertNotIn('SYS_ADMIN',logfile.read_text())
                    self.assertIn('HEAPLENS_HOST_ROOT='+str(ART.parent),logfile.read_text())

    def test_variant_options(self):
        for name in ('ascylib_efrb','ascylib_dvy','ascylib_hj','tpcc_efrb','tpcc_bcco','rocksdb_hsl','rocksdb_isl','valkey_trace'):
            for variant in ('baseline','optimized'):
                self.assertEqual(ae.parse_args(['experiment',name,'--variant',variant]).variant,variant)
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            ae.parse_args(['experiment','ascylib_efrb_bench','--variant','optimized'])
        for variant in ('segregation-only', 'prefill-only'):
            self.assertEqual(ae.parse_args(['experiment','ascylib_efrb','--variant',variant]).variant,variant)
            for name in ('ascylib_dvy', 'ascylib_hj', 'tpcc_efrb', 'rocksdb_hsl', 'valkey_trace', 'hnsw_trace'):
                with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                    ae.parse_args(['experiment',name,'--variant',variant])

    def test_overhead_options(self):
        args=ae.parse_args(['overhead','--threads','6','--duration-ms','2000',
                           '--initial','4096','--update-pct','20','--overhead-trees','efrb'])
        self.assertEqual((args.threads,args.overhead_trees),(6,['efrb']))
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            ae.parse_args(['overhead','--range','8192'])
        with self.assertRaisesRegex(ValueError,'without spaces'):
            overhead_execute(args,Path('/tmp/output with spaces'),ae)

    def test_verified_trace_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'new-events.bin';dst=Path(tmp)/'events.bin.gz'
            events=bytearray(bytes(range(40))*3)
            events[36]=1;events[76]=0;events[116]=1
            value=bytes(events);raw.write_bytes(value)
            result=archive_trace(raw,dst)
            self.assertEqual(result['records'],3)
            self.assertEqual(gzip.decompress(dst.read_bytes()),value)
            self.assertFalse(raw.exists())
            raw.write_bytes(b'bad')
            with self.assertRaises(RuntimeError):archive_trace(raw,Path(tmp)/'bad.gz')
            self.assertTrue(raw.exists())

    def test_reorder_is_narrow_and_rejects_reapplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'memtable/skiplist.h';p.parent.mkdir()
            p.write_text('prefix\n  Node** prev_;\n  int32_t prev_height_;\nsuffix\n')
            apply(tmp)
            self.assertEqual(p.read_text(),'prefix\n  int32_t prev_height_;\n  Node** prev_;\nsuffix\n')
            with self.assertRaises(RuntimeError):apply(tmp)


if __name__=='__main__':unittest.main()
