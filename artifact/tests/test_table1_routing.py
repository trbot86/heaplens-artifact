"""Command routing and actual figure settings; no application benchmarks."""
import contextlib
import hashlib
import io
import json
import os
import re
import shlex
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART))
import table1
import ae
from protocol import APPLICATIONS, schedule


class Table1Routing(unittest.TestCase):
    def test_every_readme_table1_command_routes_to_plain_corrected_drivers(self):
        section=(ART/'README.md').read_text().split('## 3.',1)[1].split('## 4.',1)[0]
        commands=[b.replace('\\\n',' ') for b in re.findall(r'```bash\n(.*?)```',section,re.S)
                  if 'table1.py reproduce' in b]
        apps=[]
        self.assertEqual(len(commands),len(APPLICATIONS))
        for command in commands:
            args=shlex.split(command)[2:]
            apps.append(args[args.index('--apps')+1])
            with patch.object(table1.launch,'main') as call, patch.object(Path,'exists',return_value=False):
                table1.main(args)
            self.assertEqual([c.args[0][0] for c in call.call_args_list],['preflight','build','run'])
            for c in call.call_args_list:
                self.assertEqual(c.args[0][c.args[0].index('--arms')+1],'plain')
        self.assertEqual(set(apps),set(APPLICATIONS))

    def test_all_rows_plain_only_and_balanced_order(self):
        cells = schedule(arms='plain')
        self.assertEqual(len(cells), 200)
        self.assertTrue(all(c['arm'] == 'plain' for c in cells))
        for app in APPLICATIONS:
            selected = [c for c in cells if c['application'] == app]
            self.assertEqual(len({c['id'] for c in selected}), 20)
            self.assertEqual([c['variant'] for c in selected[::2]], ['before', 'after'] * 5)
        self.assertEqual(len(schedule()), 400)

    def test_plan_is_read_only_and_uses_corrected_launcher(self):
        with patch.object(table1.launch.subprocess, 'check_output', side_effect=AssertionError('Docker contacted')):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                table1.main(['plan', '--apps', 'ascylib_efrb'])
        result = json.loads(out.getvalue())
        self.assertEqual((result['cells'], result['logging_cells']), (20, 0))

    def test_reproduce_routes_same_selection_and_stops_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = ['reproduce', '--apps', 'rocks_hsl', '--out', str(Path(tmp)/'out'),
                    '--data-root', str(Path(tmp)/'data'), '--acknowledge-cost']
            with patch.object(table1.launch, 'main') as call:
                table1.main(args)
            self.assertEqual([c.args[0][0] for c in call.call_args_list], ['preflight', 'build', 'run'])
            for c in call.call_args_list:
                command = c.args[0]
                self.assertEqual(command[command.index('--arms')+1], 'plain')
                self.assertEqual(command[command.index('--apps')+1], 'rocks_hsl')
            with patch.object(table1.launch, 'main', side_effect=[None, RuntimeError('build failed')]) as call:
                with self.assertRaisesRegex(RuntimeError, 'build failed'):
                    table1.main(args)
            self.assertEqual(call.call_count, 2)

    def test_existing_output_is_never_replayed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(table1.launch, 'main') as call:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                table1.main(['reproduce', '--apps', 'ascylib_efrb', '--out', tmp,
                             '--data-root', str(Path(tmp)/'data'), '--acknowledge-cost'])
            call.assert_not_called()

    def test_plain_summary_requires_complete_cells_and_native_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'data';data.mkdir();work=root/'work';work.mkdir()
            plan=schedule(['hnsw128'], 2, 'plain')
            for cell in plan:
                dest=data/cell['id'];dest.mkdir()
                raw=json.dumps({'benchmark':{'qps_mean':100 if cell['variant']=='before' else 120}}).encode()
                (dest/'result.json').write_bytes(raw)
                (dest/'portable-completed.json').write_text(json.dumps(dict(cell=cell,pmu={},result_sha256=hashlib.sha256(raw).hexdigest())))
            args=SimpleNamespace(data_root=data,work_root=work)
            table1.launch.collect_summary(args,plan)
            report=json.loads((work/'results.json').read_text())
            self.assertEqual(report['comparisons'], [])
            self.assertAlmostEqual(report['performance_comparisons'][0]['throughput_gain_pct'],20)
            (data/plan[-1]['id']/'portable-completed.json').unlink()
            with self.assertRaises(ValueError):table1.launch.collect_summary(args,plan)

    @unittest.skipUnless(sys.platform == 'linux', 'Uses the existing POSIX checkout lock')
    def test_efrb_figure_default_override_and_performance_remain_distinct(self):
        for name,override,expected in [('ascylib_efrb',None,'2'),('ascylib_efrb',7,'7'),
                                       ('ascylib_efrb_bench',None,'4')]:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                args=['experiment',name,'--profile','paper']
                if override:args+=['--threads',str(override)]
                parsed=ae.parse_args(args)
                with patch.object(ae,'ART',root), patch.object(ae,'new_output',return_value=root), \
                     patch.object(ae,'node_cpus',return_value=list(range(24))), patch.object(ae,'run') as run:
                    ae.experiment(parsed)
                self.assertEqual(run.call_args.kwargs['env']['THREADS'],expected)
                self.assertEqual(run.call_args.kwargs['env']['REPS'],'10')


if __name__ == '__main__':
    unittest.main()
