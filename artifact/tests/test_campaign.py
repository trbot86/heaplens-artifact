"""Local runner tests: no remote host, PMU permission, or model access needed."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART))
import ae
from lib import perfstat_campaign as campaign
from lib.perfstat_results import FIELDS


class CpuAndOptions(unittest.TestCase):
    topology = '# CPU,NODE,CORE,ONLINE\n2,0,0,Y\n4,0,1,Y\n6,0,2,Y\n98,0,0,Y\n100,0,1,Y\n24,1,3,Y\n8,0,4,N\n'

    def setUp(self):
        self.cpu = patch.object(ae.subprocess, 'check_output', return_value=self.topology)
        self.affinity = patch.object(ae.os, 'sched_getaffinity', return_value={2, 4, 98, 100, 24, 8}, create=True)
        self.cpu.start(); self.affinity.start()
        self.addCleanup(self.cpu.stop); self.addCleanup(self.affinity.stop)

    def test_physical_cores_obey_node_and_affinity(self):
        self.assertEqual(ae.node_cpus(0, 2), [2, 4])
        self.assertEqual(ae.node_cpus(1, 1), [24])
        self.assertEqual(ae.node_cpus(0, 2, '98,100'), [98, 100])
        with self.assertRaises(RuntimeError): ae.node_cpus(0, 3)

    def test_invalid_cpu_selections_fail(self):
        for cpus in ('2,98', '2,24', '2,6', '2,8', '2,2', '2', '2-4', '4-2', '-1', '2,9999999999999'):
            with self.subTest(cpus=cpus), self.assertRaises(ValueError):
                ae.node_cpus(0, 2, cpus)

    def test_cli_workload_reaches_experiment_environment(self):
        args = ae.parse_args(['experiment', 'ascylib_efrb_bench', '--profile', 'paper',
            '--threads', '2', '--cpus', '2,4', '--initial', '200000', '--range', '524288',
            '--duration-ms', '3000', '--update-pct', '10', '--reps', '10'])
        with tempfile.TemporaryDirectory() as tmp, patch.object(ae, 'ART', Path(tmp)), patch.object(ae, 'run') as run:
            work = Path(tmp) / 'experiments' / args.name
            work.mkdir(parents=True)
            with patch.dict(os.environ, {'THREADS': '99', 'OMP_NUM_THREADS': '1', 'ARTIFACT_NO_NUMA': '1'}):
                ae.experiment(args)
            env = run.call_args.kwargs['env']
            expected = {'THREADS': '2', 'INITIAL': '200000', 'RANGE': '524288', 'DURATION_MS': '3000',
                        'UPDATE_PCT': '10', 'REPS': '10', 'PERFBENCH_CPUS': '2,4',
                        'PERFBENCH_MEMORY': 'membind', 'PERFBENCH_ORDER': 'interleaved', 'ARTIFACT_NO_NUMA': '0'}
            for key, value in expected.items(): self.assertEqual(env[key], value, key)
            protocol = json.loads((work / 'protocol.json').read_text())
            self.assertEqual(protocol['settings']['THREADS'], '2')
            with self.assertRaises(RuntimeError): ae.experiment(args)

    def test_smoke_stays_unpinned_unless_requested(self):
        args = ae.parse_args(['experiment', 'tpcc_efrb_bench'])
        with tempfile.TemporaryDirectory() as tmp, patch.object(ae, 'ART', Path(tmp)), patch.object(ae, 'run') as run:
            (Path(tmp) / 'experiments' / args.name).mkdir(parents=True)
            ae.experiment(args)
            self.assertEqual(run.call_args.kwargs['env']['ARTIFACT_NO_NUMA'], '1')

    def test_rejects_invalid_or_inapplicable_options(self):
        cases = [['experiment', 'tpcc_efrb_bench', '--initial', '10'],
                 ['valkey', '--threads', '8'], ['experiment', 'ascylib_efrb', '--cpus', '0-1'],
                 ['all-performance', '--threads', '8'], ['rocksdb', '--threads', '1'],
                 ['experiment', 'ascylib_efrb_bench', '--update-pct', '101'],
                 ['experiment', 'ascylib_efrb_bench', '--duration-ms', '0']]
        for argv in cases:
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                ae.parse_args(argv)


class Campaign(unittest.TestCase):
    def test_ascylib_does_not_inherit_tpcc_tls_override(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp).resolve()
            binary = root / 'bench'; binary.write_bytes(b'fixture')
            plan = root / 'runs/campaign.json'
            campaign.register(argparse.Namespace(plan=plan, reps=1, variant='a', binary=binary,
                command=[str(binary)], cwd=root, preload='', library_path='', build_log=None,
                benchmark='ascylib', threads=2))
            env = json.loads(plan.read_text())['variants'][0]['environment']
            self.assertEqual(env['GLIBC_TUNABLES'], '')

    def test_valkey_bootstraps_configure_without_changing_allocator_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            jemalloc = work / 'deps/jemalloc'; jemalloc.mkdir(parents=True)
            with patch.object(ae, 'run') as run:
                ae.build_valkey(work, 2, work / 'build.log')
                self.assertEqual(run.call_args_list[0].args[0], ['autoconf'])
                self.assertEqual(run.call_args_list[0].kwargs['cwd'], jemalloc)
                make = run.call_args_list[1].args[0]
                self.assertEqual(make, ['make', '-j2', 'MALLOC=jemalloc', 'BUILD_TLS=no',
                    'BUILD_RDMA=no', 'BUILD_LUA=no', 'USE_SYSTEMD=no'])
                (jemalloc / 'configure').touch()
                run.reset_mock()
                ae.build_valkey(work, 2, work / 'build.log')
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.args[0], make)

    def test_interleaving_covers_variants_and_positions(self):
        for count in (2, 3, 4, 5):
            names = list('abcde')[:count]
            trials = campaign.schedule(names, 10, 'interleaved')
            for rep in range(10):
                self.assertEqual({name for name, r in trials if r == rep}, set(names))
            for position in range(count):
                self.assertEqual({trials[rep * count + position][0] for rep in range(count)}, set(names))
        self.assertEqual(campaign.schedule(['a', 'b'], 2, 'interleaved'), [('a', 0), ('b', 0), ('b', 1), ('a', 1)])
        self.assertEqual(campaign.schedule(['a', 'b'], 2, 'blocked'), [('a', 0), ('a', 1), ('b', 0), ('b', 1)])

    def test_saved_binary_survives_rebuild_and_trials_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / 'benchmark.py'
            plan = root / 'runs/campaign.json'
            for name, throughput in [('a', 100), ('b', 120)]:
                source.write_text('print("[summary] txn_cnt=1000,throughput={}")\n'.format(throughput))
                campaign.register(argparse.Namespace(plan=plan, reps=2, variant=name, binary=source,
                    command=[sys.executable, str(source)], cwd=root, preload='', library_path='',
                    build_log=None, benchmark='tpcc', threads=2))
            source.write_text('raise RuntimeError("The build output was replaced")\n')
            results = root / 'results.tsv'
            with results.open('w', newline='') as f: csv.writer(f, delimiter='\t').writerow(FIELDS)
            args = argparse.Namespace(plan=plan, results=results, order='interleaved', perf='off', pause_seconds=0)
            campaign.execute(args)
            with results.open() as f: rows = list(csv.DictReader(f, delimiter='\t'))
            self.assertEqual([r['variant'] for r in rows], ['a', 'b', 'b', 'a'])
            self.assertEqual([float(r['throughput_ops_s']) for r in rows], [100, 120, 120, 100])
            self.assertEqual({r['cache_misses_raw'] for r in rows}, {'NA'})
            self.assertEqual(len(list((root / 'runs').glob('*.command.json'))), 4)
            with self.assertRaises(FileExistsError): campaign.execute(args)

    def test_tpcc_comparison_uses_matching_allocator(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp) / 'results.tsv'
            with results.open('w', newline='') as f:
                writer = csv.DictWriter(f, FIELDS, delimiter='\t'); writer.writeheader()
                for name, throughput in [('a_jemalloc', 200), ('b_mimalloc', 100), ('c_mimalloc_fixed', 101),
                    ('d_single_recmgr', 240), ('e_single_recmgr_mimalloc_fixed', 122)]:
                    writer.writerow(dict(variant=name, threads=24, throughput_ops_s=throughput))
            output = io.StringIO()
            with redirect_stdout(output): campaign.summarize(argparse.Namespace(results=results))
            self.assertIn('e_single_recmgr_mimalloc_fixed / b_mimalloc: +22.00%', output.getvalue())
            self.assertIn('d_single_recmgr / a_jemalloc: +20.00%', output.getvalue())
            self.assertIn('row padding AND removal of segregation', output.getvalue())

    def test_rocks_builds_both_before_interleaved_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vendor = root / 'vendor'
            source = vendor / 'rocksdb-historical'
            (source / 'memtable').mkdir(parents=True)
            for path in (source / 'Makefile', source / 'memtable/skiplist.h'):
                path.write_text('REORDER_FIELDS NO_PADDING_NODE\n')
            allocator = vendor / 'heaplens-allocators/libjemalloc-heaplens.so'
            allocator.parent.mkdir(); allocator.write_bytes(b'allocator fixture')
            out = root / 'results'; out.mkdir()
            args = ae.parse_args(['rocksdb', '--profile', 'paper', '--reps', '2', '--threads', '18'])
            built, observed = [], []

            def fake_run(cmd, *, cwd, log, **kwargs):
                if cmd[0] == 'make':
                    (cwd / 'db_bench').write_bytes(cwd.name.encode())
                    built.append(cwd.name)
                elif cmd[0] == 'numactl':
                    self.assertEqual(built, ['baseline', 'optimized'])
                    self.assertEqual(cmd[:3], ['numactl', '--physcpubind=' + ','.join(map(str, range(18))), '--membind=0'])
                    self.assertIn('--threads=17', cmd)
                    self.assertTrue(kwargs['env']['LD_PRELOAD'].endswith('heaplens-allocators/libjemalloc-heaplens.so'))
                    self.assertIn('--benchmarks=filluniquerandom,readwhilewriting', cmd)
                    self.assertIn('--duration=60', cmd)
                    self.assertIn('--key_size=32', cmd)
                    self.assertIn('--value_size=128', cmd)
                    self.assertTrue(any(str(item).startswith('--options_file=') for item in cmd))
                    observed.append(cwd.name)
                    log.write_text('readwhilewriting : 1 micros/op 100 ops/sec\n')

            with patch.object(ae, 'VENDOR', vendor), patch.object(ae, 'run', side_effect=fake_run), \
                 patch.object(ae, 'node_cpus', return_value=list(range(18))), \
                 patch.object(ae.rocksdb_memoryonly, 'environment', return_value={'LD_PRELOAD': str(allocator)}), \
                 patch.object(ae.rocksdb_memoryonly, 'check_memory', return_value=128*1024**3), \
                 patch.object(ae.rocksdb_memoryonly, 'validate', return_value={'status': 'passed'}) as validation, \
                 patch.object(ae.time, 'sleep'), redirect_stdout(io.StringIO()):
                ae.rocksdb(args, out)
            self.assertEqual(observed, ['baseline', 'optimized', 'optimized', 'baseline'])
            self.assertEqual(validation.call_count, 4)


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux shell tests')
class ShellIntegration(unittest.TestCase):
    def test_docker_wrapper_forwards_workload_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / 'docker'
            fake.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
            fake.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + ':' + os.environ['PATH'])
            options = ['experiment', 'ascylib_efrb_bench', '--profile', 'paper', '--threads', '8',
                       '--initial', '200000', '--range', '524288', '--duration-ms', '3000', '--memory-policy', 'bind']
            output = subprocess.check_output(['bash', str(ART / 'run.sh'), *options], env=env, text=True)
            argv = json.loads(output)
            self.assertEqual(argv[argv.index('artifact/ae.py') + 1:], options)

    def test_omp_limit_does_not_reduce_pthread_count(self):
        requested = min(8, len(os.sched_getaffinity(0)))
        output = subprocess.check_output(['bash', '-c', 'source "$1"; tpcc_perfbench_cap_threads "$2"',
            'test', str(ART / 'lib/tpcc_perfbench.sh'), str(requested)],
            env=dict(os.environ, OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1'), text=True)
        self.assertEqual(int(output), requested)

    def test_tpcc_registration_records_sparse_pin_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            macro = root / 'macrobench'; (macro / 'bin').mkdir(parents=True)
            shutil.copy2(sys.executable, macro / 'bin/rundb_TPCC_test')
            # The helper archives the last build log as part of registration.
            command = 'source "$1"; TPCC_MACROBENCH="$2"; tpcc_perfbench_variant "$3/results.tsv" "$3/runs" a test 2 1'
            buildlog = root / 'build.log'
            buildlog.write_text('test build\n')
            subprocess.run(['bash', '-c', command, 'test', str(ART / 'lib/tpcc_perfbench.sh'), str(macro), str(root)],
                env=dict(os.environ, PERFBENCH_CPUS='2,4', PERFBENCH_NODE='1', PERFBENCH_MEMORY='membind',
                         TPCC_PERFBENCH_BUILD_LOG=str(buildlog), ARTIFACT_NO_NUMA='0'),
                check=True, stdout=subprocess.PIPE, text=True)
            v = json.loads((root / 'runs/campaign.json').read_text())['variants'][0]
            self.assertEqual(v['command'][:3], ['numactl', '--physcpubind=2,4', '--membind=1'])
            self.assertEqual(v['command'][-2:], ['-pin', '2.4'])
            self.assertTrue(Path(v['binary']).is_file())


if __name__ == '__main__':
    unittest.main()
