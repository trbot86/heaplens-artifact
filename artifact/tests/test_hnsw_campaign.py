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


if __name__=='__main__':unittest.main()
