"""Reproduction contracts without launching retained-input measurements."""
from contextlib import redirect_stdout, redirect_stderr
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch, Mock

ART=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ART/'camera-ready-reproduction'))
import reproduce as cr
import metrics


class Reproduction(unittest.TestCase):
    def test_plan_never_accesses_docker_or_writes(self):
        with patch.object(cr,'prepare',side_effect=AssertionError), patch.object(cr,'Docker',side_effect=AssertionError), redirect_stdout(io.StringIO()) as output:
            cr.main([])
        self.assertIn('100 Valkey',output.getvalue())

    def test_expensive_commands_require_explicit_consent(self):
        for args in (['backend','--out','x'],['sampling','--out','x'],['check'],
                     ['ui-detail','--out','x','--acknowledge-cost'],
                     ['ui-toggle','--out','x','--acknowledge-cost','--browser','missing','--playwright','missing']):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                cr.parse_args(args)

    def test_existing_output_is_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);(out/'kept').write_bytes(b'original')
            with patch.object(cr,'verify',return_value={'assets':{}}), self.assertRaises(FileExistsError):cr.prepare(out)
            self.assertEqual((out/'kept').read_bytes(),b'original')

    def test_archive_rejects_traversal_links_duplicates_and_corruption(self):
        for names,link,expected_hash in [(['../outside'],False,None),(['/absolute'],False,None),
                (['good'],True,None),(['good','good'],False,None),(['good'],False,'0'*64),(['unknown'],False,None)]:
            with self.subTest(names=names,link=link),tempfile.TemporaryDirectory() as tmp:
                archive=Path(tmp)/'a.tar';out=Path(tmp)/'out';out.mkdir()
                with tarfile.open(archive,'w') as tar:
                    for name in names:
                        info=tarfile.TarInfo(name)
                        if link:info.type=tarfile.SYMTYPE;info.linkname='../outside'
                        else:info.size=3
                        tar.addfile(info,None if link else io.BytesIO(b'abc'))
                expected={'good':dict(bytes=3,sha256=expected_hash or hashlib.sha256(b'abc').hexdigest())}
                with self.assertRaises(ValueError):cr.extract(archive,out,expected)
                self.assertFalse((Path(tmp)/'outside').exists())

    @unittest.skipIf(os.name=='nt','Linux process-group termination; Windows sandbox restricts taskkill')
    def test_timeout_preserves_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'timeout.log'
            with self.assertRaises(TimeoutError):
                cr.bounded([sys.executable,'-u','-c','import time;print("started",flush=True);time.sleep(30)'],log,0.4)
            self.assertIn('started',log.read_text())

    def test_failed_backend_does_not_start_measurements(self):
        docker=Mock();docker.command.side_effect=RuntimeError('failed self-test')
        with self.assertRaisesRegex(RuntimeError,'self-test'):cr.backend(docker,Path('/unused'))
        self.assertEqual(docker.command.call_count,1)

    def test_cleanup_attempts_each_owned_container_after_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);(out/'evidence').mkdir()
            docker=object.__new__(cr.Docker);docker.out=out;docker.owned=['owned-one','owned-two']
            def run(cmd,**kw):
                if cmd==['docker','logs','owned-one']:raise subprocess.TimeoutExpired(cmd,20)
                return subprocess.CompletedProcess(cmd,0,stderr='')
            with patch.object(cr.subprocess,'run',side_effect=run) as calls, self.assertRaises(RuntimeError):docker.close()
            removals=[c.args[0] for c in calls.call_args_list if c.args[0][1]=='rm']
            self.assertEqual(removals,[['docker','rm','-f','owned-one'],['docker','rm','-f','owned-two']])
            self.assertEqual(json.loads((out/'cleanup.json').read_text())['status'],'failed')

    def test_saved_results_recompute_paper_references(self):
        result=metrics.saved(cr.BUNDLE/'saved')
        self.assertAlmostEqual(result['backend'][0]['preparation_seconds'],105.9877995802)
        self.assertAlmostEqual(result['backend'][3]['cache_seconds'],3.6087177200)
        self.assertAlmostEqual(result['ui_toggle'][2]['baseline']['milliseconds'],570.6,places=4)
        self.assertAlmostEqual(result['ui_detail'][0]['optimized']['milliseconds'],381)
        self.assertEqual(result['sampling']['efrb']['retained'],20)

    def test_saved_integrity_detects_modified_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'saved').mkdir();(root/'saved/x.json').write_text('{}')
            (root/'manifest.json').write_text(json.dumps(dict(assets={},saved={'x.json':{'sha256':'0'*64}})))
            with self.assertRaisesRegex(ValueError,'evidence changed'):cr.verify(root)

    def test_metric_checks_reject_missing_cells_and_wrong_outputs(self):
        root=cr.BUNDLE/'saved'
        rows=metrics.read(root/'backend.json')
        with self.assertRaises(ValueError):metrics.backend(rows[:-1])
        rows[0]['payload_sha256']='wrong'
        with self.assertRaises(ValueError):metrics.backend(rows)
        rows=metrics.jsonlines(root/'toggle.jsonl');rows[0]['states']={'changed':True}
        with self.assertRaises(ValueError):metrics.toggle(rows)
        before=metrics.jsonlines(root/'detail-baseline.jsonl');after=metrics.jsonlines(root/'detail-optimized.jsonl')
        for row in after:
            if row.get('checkpoint')=='final':
                for action in row['actions']:
                    if action['label']=='brush-64k':action['state']['ui']['selected_region_bytes']=65535
        with self.assertRaises(ValueError):metrics.detail(before,after)
        rows=metrics.read(root/'sampling.json');efrb=[metrics.read(root/f'efrb-{r:02d}.json') for r in range(20)]
        rows[0]['prepared_records']=100001
        with self.assertRaises(ValueError):metrics.sampling(rows,efrb)


if __name__=='__main__':unittest.main()
