"""Baseline helper must support the pinned configure.ac-only vendor tree."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'lib/valkey_trace_support.py'
SPEC = importlib.util.spec_from_file_location('valkey_trace_support', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Bootstrap(unittest.TestCase):
    def test_bootstrap_only_when_needed(self):
        for backend, configured, expected in [('jemalloc', False, True),
                                               ('jemalloc', True, False),
                                               ('libc', False, False)]:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                dep = root / 'deps/jemalloc'
                dep.mkdir(parents=True)
                if configured:
                    (dep / 'configure').touch()
                with patch.object(MODULE, 'copy_clean_valkey'), \
                     patch.object(MODULE, 'clean_instrumented_build'), \
                     patch.object(MODULE, 'run_stream') as run:
                    MODULE.build_baseline_valkey(root, root, root / 'build.log', '2', backend)
                    calls = run.call_args_list
                    self.assertEqual(calls[0].args[0] == ['autoconf'], expected)
                    self.assertEqual(len(calls), 2 if expected else 1)
                    if expected:
                        self.assertEqual(calls[0].kwargs['cwd'], dep)


if __name__ == '__main__':
    unittest.main()
