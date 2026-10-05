"""Portable orchestration invariants; no performance workloads are launched."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

ROOT=Path(__file__).resolve().parents[2]
BUNDLE=ROOT/'artifact/headline-pmu/reproduction'
sys.path.insert(0,str(BUNDLE))
import protocol
import launch
sys.path.insert(0,str(BUNDLE/'drivers'))
import portable_runtime


class Protocol(unittest.TestCase):
    def test_complete_matrix_and_rotating_order(self):
        cells=protocol.schedule()
        self.assertEqual(len(cells),400)
        self.assertEqual(len({c['id'] for c in cells}),400)
        self.assertEqual(sum(c['arm']=='logging' for c in cells),200)
        for app in protocol.APPLICATIONS:
            for variant in ('before','after'):
                for arm in ('plain','logging'):
                    self.assertEqual({c['repetition'] for c in cells if (c['application'],c['variant'],c['arm'])==(app,variant,arm)},set(range(1,11)))
        self.assertNotEqual([c['arm'] for c in cells[:4]],[c['arm'] for c in cells[12:16]])

    def test_sparse_plan_is_explicit(self):
        self.assertEqual(len(protocol.schedule(['rocks_hsl'],1)),4)
        for apps,reps in [([],1),(['rocks_hsl']*2,1),(['missing'],1),(['valkey'],0)]:
            with self.assertRaises(ValueError):protocol.schedule(apps,reps)

    def test_default_plan_does_not_touch_docker_or_storage(self):
        with patch.object(launch.subprocess,'check_output',side_effect=AssertionError('Docker contacted')), contextlib.redirect_stdout(io.StringIO()) as output:
            launch.main([])
        self.assertEqual(json.loads(output.getvalue())['cells'],400)

    def test_topology_uses_allowed_physical_cores_and_uneven_ids(self):
        text='\n'.join(f'{100+n*100+i},{n+3},0,{n*48+i%48},Y' for n in range(2) for i in range(96))
        result=protocol.topology(text,set(range(100,396)),3,4)
        self.assertEqual(result['nodes'][0]['cpus'],list(range(100,148)))
        self.assertEqual(len(result['rocks_cpus']),96)
        self.assertEqual(result['nodes'][1]['node'],4)
        with self.assertRaises(ValueError):protocol.topology(text,{100,101},3,4)
        with self.assertRaises(ValueError):protocol.topology(text,set(range(400)),3,3,['valkey'])

    def test_smaller_subset_does_not_require_two_nodes(self):
        text='\n'.join(f'{i},5,0,{i},Y' for i in range(4))
        self.assertEqual(protocol.topology(text,set(range(4)),5,9,['ascylib_efrb'])['nodes'][0]['cpus'],list(range(4)))

    def test_source_hash_rejects_drift_accepts_checkout_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'a').write_bytes(b'one\r\ntwo\r\n')
            data=b'one\ntwo\n'
            entry=dict(override=False,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
            self.assertEqual(protocol.source_bytes(root,root,'a',entry),data)
            (root/'a').write_text('changed')
            with self.assertRaises(ValueError):protocol.source_bytes(root,root,'a',entry)

    def test_materialization_preserves_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dest=root/'existing';dest.mkdir();(dest/'keep').write_text('preserve')
            (root/'source-manifest.json').write_text(json.dumps(dict(revision=protocol.REVISION,files={})))
            with self.assertRaises(FileExistsError):protocol.materialize(root,root,dest)
            self.assertEqual((dest/'keep').read_text(),'preserve')

    def test_recorded_overrides_match_their_digests(self):
        manifest=json.loads((BUNDLE/'source-manifest.json').read_text())
        self.assertEqual(manifest['revision'],protocol.REVISION)
        self.assertGreater(len(manifest['files']),8000)
        for name,entry in manifest['files'].items():
            if entry.get('override'):protocol.source_bytes(ROOT,BUNDLE,name,entry)
        self.assertNotIn('mockup/revision.tex',manifest['files'])
        for name,row in json.loads((BUNDLE/'driver-provenance.json').read_text()).items():
            self.assertEqual(hashlib.sha256((BUNDLE/'drivers'/name).read_bytes()).hexdigest(),row['portable_sha256'],name)

    def test_sparse_retention_inventory_has_actual_selected_count(self):
        config=json.dumps(dict(plan=protocol.schedule(['rocks_hsl','hnsw128'],1)))
        with patch.object(portable_runtime.Path,'read_text',return_value=config):
            self.assertEqual(portable_runtime.expected_traces(('ascylib','tpcc','rocks')),2)
            self.assertEqual(portable_runtime.expected_traces(('hnsw',)),2)
            self.assertEqual(portable_runtime.expected_traces(('valkey',)),0)

    def test_final_summary_requires_complete_identity_set_and_native_hnsw_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'data';data.mkdir();work=root/'work';work.mkdir()
            plan=protocol.schedule(['hnsw128'],1)
            for cell in plan:
                dest=data/cell['id'];dest.mkdir()
                result=json.dumps(dict(benchmark=dict(qps_mean=100 if cell['arm']=='plain' else 80))).encode()
                (dest/'result.json').write_bytes(result)
                (dest/'portable-completed.json').write_text(json.dumps(dict(cell=cell,pmu={},result_sha256=hashlib.sha256(result).hexdigest())))
            args=SimpleNamespace(data_root=data,work_root=work)
            launch.collect_summary(args,plan)
            report=json.loads((work/'results.json').read_text())
            self.assertEqual(len(report['rows']),4)
            self.assertAlmostEqual(report['comparisons'][0]['throughput_loss_pct'],20)
            (data/plan[-1]['id']/'portable-completed.json').unlink()
            with self.assertRaises(ValueError):launch.collect_summary(args,plan)

    @unittest.skipUnless(sys.platform=='linux','Linux filesystem policy')
    def test_storage_rejects_overlap_source_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            args=SimpleNamespace(work_root=root/'work',data_root=root/'work/data',archive_root=root/'archive')
            with self.assertRaises(ValueError):launch.storage(args)
            args.data_root=root/'data';args.work_root=ROOT/'outputs'
            with self.assertRaises(ValueError):launch.storage(args)
            (root/'target').mkdir();(root/'link').symlink_to(root/'target',target_is_directory=True)
            args.work_root=root/'link'
            with self.assertRaises(ValueError):launch.storage(args)

    def test_failed_stage_has_no_retry_or_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'log';process=Mock();process.poll.return_value=3;process.returncode=3
            with patch.object(launch.subprocess,'Popen',return_value=process) as start,patch.object(launch.subprocess,'run') as stop:
                with self.assertRaises(RuntimeError):launch.bounded(['false'],log,'owned',1,None,float('inf'))
                self.assertEqual(start.call_count,1);stop.assert_not_called()
            self.assertTrue(log.exists())

    def test_timeout_stops_only_owned_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            process=Mock();process.poll.return_value=None
            with patch.object(launch.subprocess,'Popen',return_value=process),patch.object(launch.subprocess,'run') as stop:
                with self.assertRaises(TimeoutError):launch.bounded(['fake'],Path(tmp)/'log','exact-owned-name',1,None,0)
            self.assertEqual(stop.call_args.args[0],['docker','stop','-t','20','exact-owned-name'])

    def test_pmu_preflight_probe_replaces_python_entrypoint(self):
        raw=dict(topology='\n'.join(f'{i},0,0,{i},Y' for i in range(4)),allowed=list(range(4)))
        args=SimpleNamespace(server_node=0,client_node=1,apps=['ascylib_efrb'])
        with patch.object(launch.subprocess,'check_output',return_value=json.dumps(raw)),patch.object(launch.subprocess,'run',return_value=SimpleNamespace(returncode=0,stderr='counters')) as run:
            launch.preflight(args,'sha256:image')
        command=run.call_args.args[0]
        self.assertEqual(command[command.index('sha256:image')+1:][:2],['perf','stat'])

    def test_failed_pmu_probe_stops_before_workloads(self):
        raw=dict(topology='\n'.join(f'{i},0,0,{i},Y' for i in range(4)),allowed=list(range(4)))
        args=SimpleNamespace(server_node=0,client_node=1,apps=['ascylib_efrb'])
        with patch.object(launch.subprocess,'check_output',return_value=json.dumps(raw)),patch.object(launch.subprocess,'run',return_value=SimpleNamespace(returncode=1,stderr='not supported')):
            with self.assertRaisesRegex(RuntimeError,'PMU preflight'):launch.preflight(args,'image')


if __name__=='__main__':unittest.main()
