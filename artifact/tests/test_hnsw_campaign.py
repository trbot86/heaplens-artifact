"""Configuration and saved-module scheduling tests; no native builds required."""
from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ART))
import ae
from lib import hnsw_campaign as h


class Hnsw(unittest.TestCase):
    def test_physical_placement_and_dimensions(self):
        args=ae.parse_args(['hnsw','--profile','paper','--dim','1536','--hnsw-source','corrected'])
        with patch.object(ae,'node_cpus',return_value=list(range(24))) as cpu:
            config=h.configuration(args,ae)
        cpu.assert_called_once_with(0,24,None)
        self.assertEqual(config['dim'],1536)
        cmd=h.command(config,'baseline','',3)
        self.assertEqual(cmd[:3],['numactl','--physcpubind='+','.join(map(str,range(24))),'--membind=0'])
        self.assertIn('--probe',cmd);self.assertNotIn('--numa-node',cmd)
        self.assertEqual(cmd[cmd.index('--build-threads')+1],'24')
        self.assertEqual(cmd[cmd.index('--iterations')+1],'5')

    def test_existing_defaults_and_smoke(self):
        args=ae.parse_args(['hnsw'])
        config=h.configuration(args,ae)
        self.assertEqual((config['dim'],config['elements'],config['queries']),(128,10000,1000))
        self.assertIsNone(config['cpus'])
        args=ae.parse_args(['hnsw-factorization'])
        self.assertEqual(h.configuration(args,ae)['dim'],768)
        with patch.dict(os.environ,{'LD_PRELOAD':'unrelated.so','PYTHONPATH':'/other','HNSWLIB_NO_NATIVE':'1'}):
            env=h.runtime_environment()
        self.assertNotIn('LD_PRELOAD',env);self.assertNotIn('PYTHONPATH',env);self.assertNotIn('HNSWLIB_NO_NATIVE',env)

    def test_dimension_defaults_and_explicit_overrides(self):
        for argv,expected in (
            (['hnsw','--profile','paper'],[128,1536]),
            (['hnsw'],[128]),
            (['hnsw','--profile','paper','--dim','768','--hnsw-source','original'],[768]),
            (['hnsw','--dim','1536'],[1536]),
            (['hnsw-factorization','--profile','paper'],[768]),
            (['hnsw-factorization','--factors','alignment','--profile','paper'],[768]),
            (['hnsw-factorization','--dim','128'],[128])):
            with self.subTest(argv=argv):self.assertEqual(h.dimensions(ae.parse_args(argv)),expected)

    def test_two_dimension_order(self):
        execution=[(label,b) for b in range(1,11) for label in
                   (['baseline','vector_huge'] if b%2 else ['vector_huge','baseline'])]
        actual=h.dimensional_execution(execution,[128,1536])
        expected=[(dim,label,b) for b in range(1,11)
                  for dim in ([128,1536] if b%2 else [1536,128])
                  for label in (['baseline','vector_huge'] if b%2 else ['vector_huge','baseline'])]
        self.assertEqual(actual,expected)
        self.assertEqual(len(set(actual)),40)
        blocked=[('baseline',1),('baseline',2),('vector_huge',1),('vector_huge',2)]
        self.assertEqual(h.dimensional_execution(blocked,[128,1536],True),
                         [(d,v,b) for d in [128,1536] for v,b in blocked])

    def test_option_boundaries(self):
        for argv in (['valkey','--dim','128'],['hnsw','--dim','0'],
                     ['hnsw-factorization','--hnsw-source','original'],
                     ['hnsw-factorization','--trial-order','blocked'],
                     ['experiment','ascylib_efrb_bench','--hj-jemalloc','5.3']):
            with self.subTest(argv=argv),redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):ae.parse_args(argv)

    def test_hj_allocator_reaches_recorded_protocol(self):
        for version in (None,'5.0','5.3'):
            argv=['experiment','ascylib_hj_bench']+(['--hj-jemalloc',version] if version else [])
            args=ae.parse_args(argv)
            with tempfile.TemporaryDirectory() as tmp,patch.object(ae,'ART',Path(tmp)),patch.object(ae,'run') as run,patch.object(ae.os,'sched_getaffinity',return_value={0,1},create=True):
                dest=Path(tmp)/'experiments'/args.name;dest.mkdir(parents=True)
                ae.experiment(args)
                self.assertEqual(run.call_args.kwargs['env']['HJ_JEMALLOC'],version or '5.3')
                self.assertEqual(json.loads((dest/'protocol.json').read_text())['settings']['HJ_JEMALLOC'],version or '5.3')

    def test_builds_all_cells_before_running_and_keeps_blocks(self):
        args=ae.parse_args(['hnsw','--reps','2','--hnsw-source','corrected','--dim','128'])
        events=[]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);vendor=root/'vendor';source=vendor/'hnswlib-corrected';source.mkdir(parents=True)
            (source/'benchmark.py').write_text('# fixture')
            out=root/'results';out.mkdir()
            def fake_run(cmd,**kwargs):
                if 'build_ext' in cmd:
                    events.append(('build',kwargs['cwd'].name))
                    (kwargs['cwd']/'hnswlib-test.so').write_bytes(b'fixture-'+kwargs['cwd'].name.encode())
                else:
                    self.assertEqual(len([e for e in events if e[0]=='build']),2)
                    label=next(x.split('=',1)[1] for x in cmd if x.startswith('--variant-label='))
                    defines=next(x.split('=',1)[1] for x in cmd if x.startswith('--variant-defines='))
                    block=int(cmd[cmd.index('--repetition')+1]);events.append(('run',label,block))
                    config=h.configuration(args,ae)
                    row={k:config[k] for k in ('dim','threads','build_threads','elements','queries','m','ef_construction','ef','k','warmup','iterations','query_mode')}
                    row.update(variant=label,defines=defines,repetition=block,timed_queries=1000,deleted=0,
                               qps_mean=1000.0,query_seconds=1.0,recall_mean=0.5)
                    Path(kwargs['log']).write_text(json.dumps(row)+'\n')
            with patch.object(ae,'VENDOR',vendor),patch.object(ae,'run',side_effect=fake_run):ae.hnsw(args,out)
            self.assertEqual(events[2:],[('run','baseline',1),('run','vector_huge',1),('run','vector_huge',2),('run','baseline',2)])
            self.assertEqual(len(list(out.glob('block*.csv'))),4)
            self.assertEqual(json.loads((out/'summary.json').read_text())['source'],'hnswlib-corrected')
            self.assertEqual(json.loads((out/'protocol.json').read_text())['configuration']['dim'],128)

    def test_bad_denominator_rejected(self):
        args=ae.parse_args(['hnsw']);config=h.configuration(args,ae)
        row={k:config[k] for k in ('dim','threads','build_threads','elements','queries','m','ef_construction','ef','k','warmup','iterations','query_mode')}
        row.update(variant='baseline',defines='',repetition=1,timed_queries=1000,deleted=0,qps_mean=1000.,query_seconds=2.)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'log';path.write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError,'denominator'):h.read_result(path,config,'baseline','',1)

    def test_paper_campaign_builds_once_and_summarizes_each_dimension(self):
        args=ae.parse_args(['hnsw','--profile','paper'])
        events=[]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);vendor=root/'vendor';source=vendor/'hnswlib-corrected';source.mkdir(parents=True)
            (source/'benchmark.py').write_text('# fixture')
            out=root/'results';out.mkdir()
            def fake_run(cmd,**kwargs):
                if 'build_ext' in cmd:
                    events.append(('build',kwargs['cwd'].name))
                    (kwargs['cwd']/'hnswlib-test.so').write_bytes(b'fixture-'+kwargs['cwd'].name.encode())
                    return
                self.assertEqual(len([e for e in events if e[0]=='build']),2)
                label=next(x.split('=',1)[1] for x in cmd if x.startswith('--variant-label='))
                defines=next(x.split('=',1)[1] for x in cmd if x.startswith('--variant-defines='))
                block=int(cmd[cmd.index('--repetition')+1]);dim=int(cmd[cmd.index('--dims')+1])
                events.append(('run',dim,label,block))
                config=h.configuration(args,ae,dim)
                row={k:config[k] for k in ('dim','threads','build_threads','elements','queries','m','ef_construction','ef','k','warmup','iterations','query_mode')}
                qps=(10000 if dim==128 else 1000)*(1 if label=='baseline' else (1.10 if dim==128 else 1.05))
                row.update(variant=label,defines=defines,repetition=block,timed_queries=500000,deleted=0,
                           qps_mean=qps,query_seconds=500000/qps,recall_mean=0.5)
                Path(kwargs['log']).write_text(json.dumps(row)+'\n')
            with patch.object(ae,'VENDOR',vendor),patch.object(ae,'run',side_effect=fake_run),\
                 patch.object(ae,'node_cpus',return_value=list(range(24))),patch.object(h.time,'sleep'):
                ae.hnsw(args,out)
            self.assertEqual(len(events),42)
            self.assertEqual(len(list(out.glob('block*.csv'))),40)
            protocol=json.loads((out/'protocol.json').read_text())
            self.assertEqual(protocol['dimensions'],[128,1536])
            self.assertEqual(set(protocol['configurations']),{'128','1536'})
            self.assertNotIn('configuration',protocol)
            self.assertEqual(events[2:],[('run',e['dim'],e['variant'],e['block']) for e in protocol['trial_sequence']])
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['source'],'hnswlib-corrected')
            self.assertNotIn('variants',summary)  # No pooled cross-dimension throughput.
            for dim,gain in [('128',10),('1536',5)]:
                variants=summary['by_dimension'][dim]['variants']
                self.assertEqual(variants['baseline']['runs'],10)
                self.assertEqual(variants['vector_huge']['runs'],10)
                self.assertAlmostEqual(variants['vector_huge']['change_percent_vs_baseline'],gain)

    def test_original_source_remains_selectable(self):
        args=ae.parse_args(['hnsw','--hnsw-source','original','--dim','768'])
        with tempfile.TemporaryDirectory() as tmp,patch.object(h,'execute',return_value={'baseline':[1.0],'vector_huge':[1.0]}) as execute:
            ae.hnsw(args,Path(tmp))
            self.assertEqual(execute.call_args.args[2].name,'hnswlib')
            self.assertEqual(json.loads((Path(tmp)/'summary.json').read_text())['dimensions'],[768])

    def test_umbrella_uses_both_paper_dimensions(self):
        observed=[]
        def capture(args,out):
            observed.append((args.command,h.dimensions(args),args.hnsw_source))
        with patch.object(sys,'argv',['ae.py','all-performance','--profile','paper']),\
             patch.object(ae,'experiment'),patch.object(ae,'valkey'),patch.object(ae,'rocksdb'),\
             patch.object(ae,'new_output'),patch.object(ae,'hnsw',side_effect=capture):
            ae.main()
        self.assertEqual(observed,[('hnsw',[128,1536],None)])


if __name__=='__main__':unittest.main()
