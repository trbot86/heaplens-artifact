"""End-to-end allocation metadata checks, independent of successful compilation."""
from collections import Counter
import json
import os
from pathlib import Path
import re
import struct
import tempfile
import unittest

from test_project_header_logging import ROOT, run


@unittest.skipUnless(os.getenv('HEAPLENS_RUN_INSTRUMENTATION_TESTS') == '1',
                     'opt-in native toolchain test')
class NewExpressionLogging(unittest.TestCase):
    def test_nested_allocations_arrays_exceptions_and_alignment(self):
        base = Path(os.environ.get('HEAPLENS_TEST_EVIDENCE', tempfile.gettempdir()))
        trial = Path(tempfile.mkdtemp(prefix='new-expressions-', dir=base))
        source = trial/'input'; source.mkdir(); target = trial/'project'
        (source/'main.cpp').write_bytes((ROOT/'artifact/tests/fixtures/new_expression_logging.cpp').read_bytes())
        flags = ' -I/root/sifter/memhook main.cpp -L/root/sifter/memhook -Wl,-rpath=/root/sifter/memhook -lmemhook -ldl -pthread -o probe'
        (source/'Makefile').write_text('all:\n\tg++ -std=c++17 -O0'+flags+'\n')
        (trial/'clean.log').write_text(run(['make', 'clean'], ROOT/'memhook'))
        (trial/'driver.log').write_text(run(['bash', 'sifter.sh', str(source), str(target), '-t', '--skip-refactor']))
        run(['clang-apply-replacements-14', str(target)])
        run(['bash', 'sifter.sh', str(target), '--includes-only'])
        # C++11 deliberately checks that the fix does not depend on C++17's
        # operand sequencing. All evidence stays in a fresh run directory.
        for standard, optimization in [('c++11', '-O0'), ('c++17', '-O2')]:
            cell = trial/standard; cell.mkdir()
            command = ['g++', '-std='+standard, optimization, *flags.split()]
            (cell/'build.log').write_text(run(command, target))
            output = run([str(target/'probe')], cell)
            (cell/'output.txt').write_text(output)
            expected = [(t, int(p,16), int(n), int(f)) for t,p,n,f in re.findall(
                r'EXPECT (\w+) (0x[0-9a-f]+) (\d+) (\d+)', output)]
            self.assertGreaterEqual(len(expected), 80)
            records = list(struct.iter_unpack('<QQQQHH?3x', (cell/'binary_dump.txt').read_bytes()))
            records.sort(key=lambda r:r[1]) # buffers from different threads drain separately
            self.assertTrue(all(r[3] != 0 for r in records if r[6]), 'failed allocation was logged')
            types = {int(i):s for i,s in (line.split('|',1) for line in
                     (cell/'typeset_dump.txt').read_text().splitlines())}
            names = {e[0] for e in expected}
            actual = [(types.get(r[5]), r[3], r[2]) for r in records if r[6] and types.get(r[5]) in names]
            (cell/'comparison.json').write_text(json.dumps(dict(expected=expected, actual=actual), indent=2)+'\n')
            self.assertEqual(Counter(actual), Counter((t,p,n) for t,p,n,f in expected))
            # malloc scratch space can be freed and reused by a later typed
            # object. Check each allocation's lifetime, not all frees ever
            # recorded at its address.
            wanted = {(t,p):f for t,p,n,f in expected}
            checked_frees = 0
            for i,r in enumerate(records):
                if not r[6] or types.get(r[5]) not in names:
                    continue
                end = next((j for j in range(i+1,len(records))
                            if records[j][6] and records[j][3] == r[3]), len(records))
                count = sum(not x[6] and x[3] == r[3] for x in records[i+1:end])
                self.assertEqual(count, wanted[(types[r[5]],r[3])])
                checked_frees += count
            (cell/'verification.json').write_text(json.dumps(dict(
                standard=standard, optimization=optimization, allocations=len(expected),
                checked_frees=checked_frees), indent=2)+'\n')

    def test_rejects_unsupported_storage_array_without_partial_edits(self):
        base = Path(os.environ.get('HEAPLENS_TEST_EVIDENCE', tempfile.gettempdir()))
        trial = Path(tempfile.mkdtemp(prefix='placement-array-', dir=base))
        source = trial/'input'; source.mkdir(); target = trial/'project'
        cpp = '#include <new>\nint main() { alignas(long) char data[80]; new(data) long[10]; }\n'
        (source/'main.cpp').write_text(cpp)
        (source/'Makefile').write_text('all:\n\tg++ -std=c++11 -c main.cpp\n')
        with self.assertRaises(AssertionError) as failure:
            run(['bash', 'sifter.sh', str(source), str(target), '-t', '--skip-refactor'])
        (trial/'driver.log').write_text(str(failure.exception))
        self.assertIn('placement-new arrays require an explicit extent hook', str(failure.exception))
        self.assertEqual((target/'main.cpp').read_text(), cpp)
