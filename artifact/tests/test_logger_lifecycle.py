"""Tiny native Linux logger correctness tests; no PMU or benchmark runs."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(sys.platform.startswith('linux') and shutil.which('g++'),
                     'requires Linux and g++')
class LoggerLifecycle(unittest.TestCase):
    def test_real_header_lifecycle_and_faults(self):
        with tempfile.TemporaryDirectory(prefix='heaplens-logger-test-') as tmp:
            binary = Path(tmp) / 'test'
            subprocess.run(['g++', '-std=c++11', '-DMEMHOOK_MAX_BUFFER_SIZE=4',
                            '-I' + str(ROOT / 'memhook'),
                            str(ROOT / 'artifact/tests/fixtures/logger_lifecycle.cpp'),
                            '-pthread', '-lrt', '-o', str(binary),
                            '-Wl,--wrap=aio_write,--wrap=aio_error,--wrap=aio_suspend,--wrap=aio_return'],
                           check=True, timeout=60)
            for count in (0, 1, 4, 5, 40, 43):
                for fault in (0, 1):
                    result = subprocess.run([str(binary), str(count), str(fault),
                                             str(Path(tmp) / f'{count}-{fault}.bin')],
                                            capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
            for fault in (2, 3, 4, 5):
                result = subprocess.run([str(binary), '12', str(fault),
                                         str(Path(tmp) / f'fault-{fault}.bin')],
                                        capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 94, result.stderr)
                self.assertIn(b'trace invalid', result.stderr)


if __name__ == '__main__':
    unittest.main()
