"""DVY isolation, missing-runtime fallback and page-check behavior."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART))
import ae
from lib import dvy_runtime as dvy


def plan_at(root):
    variants = []
    for name in ('a_96B_default', 'b_72B_no_pad', 'c_128B_pad', 'd_192B_pad'):
        binary = root / name; binary.write_bytes(b'test binary')
        variants.append(dict(name=name, benchmark='ascylib', binary=str(binary), cwd=str(root),
            command=['numactl', '--physcpubind=2,4', '--interleave=1', str(binary), '-d', '5000'],
            environment={'LD_PRELOAD': '', 'LD_LIBRARY_PATH': '/old/library', 'GLIBC_TUNABLES': 'unrelated=1'}))
    path = root / 'campaign.json'
    path.write_text(json.dumps(dict(variants=variants)))
    return path


class Dvy(unittest.TestCase):
    def test_default_and_scope(self):
        self.assertIsNone(ae.parse_args(['experiment', 'ascylib_dvy_bench']).dvy_hugepages)
        self.assertEqual(ae.parse_args(['experiment', 'ascylib_dvy_bench', '--dvy-hugepages', 'off']).dvy_hugepages, 'off')
        for cmd in (['hnsw'], ['experiment', 'ascylib_efrb_bench'], ['experiment', 'tpcc_bcco_bench']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                ae.parse_args(cmd + ['--dvy-hugepages', 'require'])

    def test_missing_bundle_uses_one_recorded_fallback(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as warnings:
            root = Path(tmp); path = plan_at(root)
            dvy.configure(path, bundle=root / 'absent')
            plan = json.loads(path.read_text()); self.assertFalse(plan['dvy_runtime']['bundled'])
            self.assertIn('rebuild', warnings.getvalue())
            for v in plan['variants']:
                self.assertEqual(v['command'][3:5], ['/usr/bin/env', 'GLIBC_TUNABLES=glibc.malloc.hugetlb=1'])
                self.assertEqual(v['command'][5], v['binary'])
                self.assertFalse(any(v['environment'].values()))
            with self.assertRaises(ValueError): dvy.configure(path)

    def test_bundle_only_wraps_benchmark_and_records_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = plan_at(root); bundle = root / 'runtime'; bundle.mkdir()
            for name in dvy.LIBRARIES: (bundle / name).write_bytes(name.encode())
            with patch.object(dvy.subprocess, 'check_output', return_value='test runtime'):
                dvy.configure(path, 'off', 'paper', bundle)
            plan = json.loads(path.read_text()); self.assertTrue(plan['dvy_runtime']['bundled'])
            self.assertEqual(len(plan['dvy_runtime']['libraries']), 7)
            for v in plan['variants']:
                self.assertEqual(v['command'][:3], ['numactl', '--physcpubind=2,4', '--interleave=1'])
                self.assertEqual(v['command'][3:10], ['/usr/bin/env', 'GLIBC_TUNABLES=glibc.malloc.hugetlb=0',
                    str(bundle / 'ld-linux-x86-64.so.2'), '--inhibit-cache', '--library-path', str(bundle), v['binary']])

    def test_unloadable_bundle_falls_back_for_entire_campaign(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            root = Path(tmp); path = plan_at(root); bundle = root / 'runtime'; bundle.mkdir()
            for name in dvy.LIBRARIES: (bundle / name).touch()
            with patch.object(dvy.subprocess, 'check_output', side_effect=OSError('unsupported')):
                dvy.configure(path, bundle=bundle)
            plan = json.loads(path.read_text())
            self.assertFalse(plan['dvy_runtime']['bundled'])
            self.assertTrue(all(str(bundle) not in ' '.join(v['command']) for v in plan['variants']))

    def test_no_huge_pages_warns_by_default_and_strict_stops(self):
        for mode in ('auto', 'require', 'off'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp, \
                 contextlib.redirect_stderr(io.StringIO()) as warnings, contextlib.redirect_stdout(io.StringIO()):
                root = Path(tmp); path = plan_at(root)
                dvy.configure(path, mode, 'paper', root / 'absent')
                plan = json.loads(path.read_text())
                proc = MagicMock(pid=9999999999999); proc.wait.return_value = 0; proc.poll.return_value = 0
                with patch.object(dvy.subprocess, 'Popen', return_value=proc), patch.object(dvy.time, 'sleep'):
                    if mode == 'require':
                        with self.assertRaisesRegex(RuntimeError, 'Strict mode stopped'): dvy.diagnose(plan, root)
                    else: dvy.diagnose(plan, root)
                summary = json.loads((root / 'dvy-page-checks/summary.json').read_text())
                self.assertEqual(len(summary['rows']), 4)
                self.assertEqual(summary['status'], 'huge_backing_not_confirmed_all_layouts')
                if mode == 'auto': self.assertIn('may not reproduce', warnings.getvalue())

    def test_small_smoke_skips_extra_processes(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            root = Path(tmp); path = plan_at(root); dvy.configure(path, bundle=root / 'absent')
            with patch.object(dvy.subprocess, 'Popen') as proc:
                result = dvy.diagnose(json.loads(path.read_text()), root)
                proc.assert_not_called()
            self.assertEqual(result['status'], 'not_checked_small_smoke_workload')

    def test_smaps_totals_and_flags(self):
        self.assertEqual(dvy.mapping_values('AnonHugePages: 2048 kB\nAnonymous: 3000 kB\nRss: 3500 kB\nVmFlags: rd hg\n'
            'AnonHugePages: 4096 kB\nAnonymous: 4500 kB\nRss: 5000 kB\nVmFlags: rd\n'),
            dict(AnonHugePages=6144, Anonymous=7500, Rss=8500, huge_advised_mappings=1))

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux environment runner')
    def test_child_really_receives_glibc_tunables(self):
        for mode,value in [('auto','1'),('require','1'),('off','0')]:
            with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
                root=Path(tmp);path=plan_at(root)
                dvy.configure(path, mode, bundle=root/'absent')
                command=json.loads(path.read_text())['variants'][0]['command']
                env_prefix=command[3:5]
                actual=subprocess.check_output([*env_prefix,sys.executable,'-c',
                    'import os; print(os.environ.get("GLIBC_TUNABLES", "MISSING"))'],
                    env=dvy.clean_environment(),text=True).strip()
                self.assertEqual(actual,'glibc.malloc.hugetlb='+value)

    def test_unrelated_campaign_cannot_opt_in_accidentally(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = plan_at(root); plan = json.loads(path.read_text())
            plan['variants'][0]['name'] = 'efrb'; path.write_text(json.dumps(plan))
            with self.assertRaises(ValueError): dvy.configure(path)


if __name__ == '__main__': unittest.main()
