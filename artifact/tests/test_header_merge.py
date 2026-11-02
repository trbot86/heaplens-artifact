"""Conflicting annotations must not silently select one translation unit."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import yaml
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('annotation_runner',ROOT/'clang-tidy-standalone/tool/run-clang-tidy.py')
runner=importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)


class HeaderMerge(unittest.TestCase):
    def test_failed_translation_unit_never_applies_fixes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'compile_commands.json').write_text(json.dumps([dict(directory=temp,
                file=str(root/'main.cpp'),command='c++ main.cpp')]))
            (root/'main.cpp').write_text('int main() {}\n')
            tidy=root/'tidy'; apply=root/'apply'
            tidy.write_text('#!/bin/sh\ncase "$*" in *-list-checks*) exit 0;; esac\nexit 3\n')
            apply.write_text('#!/bin/sh\n[ "$1" = "--version" ] && exit 0\ntouch "'+str(root/'applied')+'"\n')
            tidy.chmod(0o755); apply.chmod(0o755)
            result=subprocess.run([sys.executable,str(ROOT/'clang-tidy-standalone/tool/run-clang-tidy.py'),
                '-j','1','-p',temp,'-clang-tidy-binary',str(tidy),
                '-clang-apply-replacements-binary',str(apply),'-fix'],capture_output=True,text=True,timeout=15)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((root/'applied').exists())
            self.assertIn('no edits applied',result.stderr)

    def test_conflicting_replacements_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for i,text in enumerate(('MemStamp(1, 4) * ','MemStamp(2, 4) * ')):
                (root/f'{i}.yaml').write_text(yaml.safe_dump({'Diagnostics':[{
                    'DiagnosticName':'misc-allocation-logging','DiagnosticMessage':{
                        'FilePath':'/project/shared.h','FileOffset':42,
                        'Replacements':[{'FilePath':'/project/shared.h','Offset':42,
                                         'Length':0,'ReplacementText':text}]}}]}))
            with self.assertRaisesRegex(RuntimeError,'[Cc]onflict'):
                runner.merge_no_duplicates(str(root),str(root/'out.yaml'))
