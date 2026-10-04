"""Opt-in native protocol regression; no PMU/performance measurement.

HEAPLENS_NATIVE_VALKEY_TEST=1 python3 -m unittest discover -s artifact/tests
-p test_valkey_terminal.py -v. Requires Linux, make, C/C++ compilers.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'artifact/lib'))
import valkey_terminal
import valkey_trace_support as support


class SourcePatch(unittest.TestCase):
    def test_controller_accepts_only_successful_finalization(self):
        for replies, success in [([b'+OK\r\n'], True),
                                 ([b'-ERR HeapLENS producers not quiescent or already finalized\r\n',
                                   b'+OK\r\n'], True),
                                 ([b'-ERR unknown command\r\n'], False),
                                 ([b''], False)]:
            connection = MagicMock()
            connection.__enter__.return_value = connection
            connection.makefile.return_value.readline.side_effect = replies
            process = MagicMock()
            process.poll.return_value = None
            with patch.object(support.socket, 'create_connection', return_value=connection), \
                 patch.object(support.time, 'sleep'):
                if success:
                    support.finish_trace_producers(1, process)
                else:
                    with self.assertRaises(support.BenchmarkError):
                        support.finish_trace_producers(1, process)

    def test_pinned_anchors_and_reject_reapplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            for name in ('io_threads.h', 'io_threads.c', 'bio.c', 'debug.c'):
                shutil.copyfile(ROOT / 'artifact/vendor/valkey/src' / name, root / 'src' / name)
            valkey_terminal.patch_source(root)
            before = {p: p.read_bytes() for p in (root / 'src').iterdir()}
            with self.assertRaises(ValueError):
                valkey_terminal.patch_source(root)
            self.assertEqual(before, {p: p.read_bytes() for p in before})


@unittest.skipUnless(sys.platform.startswith('linux') and
                     os.environ.get('HEAPLENS_NATIVE_VALKEY_TEST') == '1',
                     'opt-in native Valkey build')
class NativeTerminal(unittest.TestCase):
    def test_workers_flush_actual_logger(self):
        with tempfile.TemporaryDirectory(prefix='heaplens-valkey-terminal-') as tmp:
            root = Path(tmp)
            source = root / 'valkey'
            shutil.copytree(ROOT / 'artifact/vendor/valkey', source,
                            ignore=shutil.ignore_patterns('.git', '*.o', '*.a', 'valkey-server', 'valkey-cli'))
            valkey_terminal.patch_source(source)
            for name in ('io_threads.c', 'bio.c'):
                p = source / 'src' / name
                p.write_text(p.read_text().replace('memhook_terminal_flush', 'heaplens_test_finish'))
            library = root / 'libmemhook.so'
            subprocess.run(['g++', '-std=c++11', '-fPIC', '-shared', '-pthread',
                            '-I' + str(ROOT / 'memhook'), str(ROOT / 'memhook/memhook.cpp'),
                            str(ROOT / 'memhook/hash.cpp'),
                            str(ROOT / 'artifact/tests/fixtures/valkey_terminal_probe.cpp'),
                            '-ldl', '-lrt', '-o', str(library)], check=True, timeout=60)
            makefile = source / 'src/Makefile'
            makefile.write_text(makefile.read_text() +
                                f'\nFINAL_LIBS += -L{root} -Wl,-rpath,{root} -lmemhook\n')
            with (root / 'build.log').open('w') as log:
                build = subprocess.run(['make', '-j2', 'MALLOC=libc', 'BUILD_TLS=no',
                                        'BUILD_RDMA=no', 'BUILD_LUA=no', 'USE_SYSTEMD=no',
                                        'OPTIMIZATION=-O1',
                                        'valkey-server'], cwd=source, stdout=log,
                                       stderr=subprocess.STDOUT, timeout=600)
            self.assertEqual(build.returncode, 0, (root / 'build.log').read_text()[-12000:])
            for threads in (1, 4):
                output = root / f'events-{threads}.bin'
                with socket.socket() as reservation:
                    reservation.bind(('127.0.0.1', 0))
                    port = reservation.getsockname()[1]
                env = dict(os.environ, MEMHOOK_OUTPUT_DUMP_FILE=str(output))
                with (root / f'server-{threads}.log').open('w') as log:
                    proc = subprocess.Popen([str(source / 'src/valkey-server'),
                                             '--bind', '127.0.0.1', '--port', str(port),
                                             '--save', '', '--appendonly', 'no',
                                             '--io-threads', str(threads),
                                             '--io-threads-always-active', 'yes',
                                             '--enable-debug-command', 'yes'],
                                            env=env, cwd=root, stdout=log, stderr=log)
                    try:
                        for attempt in range(100):
                            try:
                                sock = socket.create_connection(('127.0.0.1', port), timeout=1)
                                break
                            except OSError:
                                if proc.poll() is not None: self.fail('server exited during startup')
                                time.sleep(.05)
                        else: self.fail('server startup timeout')
                        with sock:
                            sock.settimeout(5)
                            stream = sock.makefile('rb')
                            for i in range(100):
                                sock.sendall(f'SET key{i} value\r\n'.encode())
                                self.assertEqual(stream.readline(), b'+OK\r\n')
                        support.finish_trace_producers(port, proc)
                        with socket.create_connection(('127.0.0.1', port), timeout=5) as end:
                            end.sendall(b'SHUTDOWN NOSAVE\r\n')
                        self.assertEqual(proc.wait(timeout=15), 0)
                    finally:
                        if proc.poll() is None:
                            proc.terminate()
                            try: proc.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                proc.kill(); proc.wait()
                raw = output.read_bytes()
                self.assertEqual(len(raw) % 40, 0)
                tids = [struct.unpack_from('<Q', raw, i)[0] for i in range(0, len(raw), 40)
                        if struct.unpack_from('<Q', raw, i+8)[0] == 0x484c54455354]
                self.assertEqual(len(tids), threads + 5)
                self.assertEqual(len(set(tids)), len(tids))


if __name__ == '__main__':
    unittest.main()
