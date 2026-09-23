"""Counter-reporting regression tests; no PMU access or benchmark build needed.

Run from the repository root: python3 -m unittest discover -s artifact/tests -v
"""

import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ARTIFACT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ARTIFACT / "lib"))
from perfstat_results import FIELDS, make_row, parse_benchmark, parse_counters


# A three-second run: '#txs' is rounded operations/second, NOT the denominator.
ASCY = """srch: 240000 | 120000 | 50.0% |
insr: 40000 | 10000 | 25.0% |
rems: 20000 | 10000 | 50.0% |
#txs 2 (100000
#Mops 0.100
"""
TPCC = """[tid=0] txn_cnt=80000,abort_cnt=20000
Per-index stats: totalOps=99999, throughput=99999
[summary] txn_cnt=200000, abort_cnt=50000, run_time=6, ixThroughput=9999, nthreads=2, throughput=66666.666667
"""
PERF = """# perf stat -x, output
600000,,cache-misses,3000000000,100.00,,
0,,page-faults,3000000000,100.00,,
<not supported>,,L1-dcache-load-misses,0,100.00,,
300000.5,,LLC-load-misses,3000000000,100.00,,
<not counted>,,LLC-store-misses,0,100.00,,
3000,,context-switches,3000000000,100.00,,
"""


class CounterTests(unittest.TestCase):
    def test_ascylib_uses_operation_totals_not_txs_or_successes(self):
        count, throughput, unit = parse_benchmark(ASCY, "ascylib")
        self.assertEqual(count, 300000)
        self.assertEqual(throughput, 100000)
        self.assertEqual(unit, "tree_operation")
        row = make_row("ascylib", ASCY, PERF, "baseline", 2, 0)
        self.assertEqual(row["cache_misses_raw"], "600000")
        self.assertEqual(float(row["cache_misses_per_op"]), 2)
        self.assertEqual(float(row["context_switches_per_op"]), .01)

    def test_tpcc_uses_global_committed_count(self):
        row = make_row("tpcc", TPCC, PERF, "baseline", 2, 0)
        self.assertEqual(row["operation_count"], 200000)
        self.assertEqual(row["operation_unit"], "committed_transaction")
        self.assertEqual(row["throughput_ops_s"], "66666.6667")
        self.assertEqual(float(row["cache_misses_per_op"]), 3)

    def test_missing_and_disabled_counters_remain_na(self):
        row = make_row("ascylib", ASCY, PERF, "x", 2, 0)
        for name in ("l1d_misses", "llc_store_misses", "dtlb_misses"):
            self.assertEqual(row[name + "_raw"], "NA")
            self.assertEqual(row[name + "_per_op"], "NA")
        self.assertEqual(row["page_faults_raw"], "0")
        self.assertEqual(float(row["page_faults_per_op"]), 0)
        self.assertEqual(float(row["llc_load_misses_raw"]), 300000.5)
        self.assertAlmostEqual(float(row["llc_load_misses_per_op"]), 300000.5 / 300000)
        self.assertEqual(set(parse_counters("").values()), {"NA"})

    def test_count_is_independent_of_throughput(self):
        slow = make_row("tpcc", TPCC, PERF, "x", 2, 0)
        fast = make_row("tpcc", TPCC.replace("throughput=66666.666667", "throughput=100000"),
                        PERF, "y", 2, 0)
        self.assertNotEqual(slow["throughput_ops_s"], fast["throughput_ops_s"])
        self.assertEqual(slow["cache_misses_per_op"], fast["cache_misses_per_op"])

    def test_rejects_missing_zero_or_ambiguous_denominators(self):
        for text, kind in (("#Mops 1\n", "ascylib"),
                           (ASCY + "srch: 2 | 1 |\n", "ascylib"),
                           (TPCC.replace("txn_cnt=200000", "txn_cnt=0"), "tpcc"),
                           (TPCC + TPCC, "tpcc"),
                           (TPCC.replace("throughput=66666.666667", "throughput=0"), "tpcc")):
            with self.subTest(kind=kind, text=text), self.assertRaises(ValueError):
                parse_benchmark(text, kind)

    def test_duplicate_event_is_not_silently_discarded(self):
        with self.assertRaises(ValueError):
            parse_counters(PERF + "100,,cache-misses,1,100,,\n")

    def test_failed_parse_does_not_append_a_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            helper = str(ARTIFACT / "lib/perfstat_results.py")
            header = subprocess.check_output([sys.executable, helper, "header"])
            (root / "results.tsv").write_bytes(header)
            (root / "benchmark.log").write_text("#Mops 1\n")
            (root / "perf.csv").write_text(PERF)
            result = subprocess.run([
                sys.executable, helper, "append", "--benchmark", "ascylib",
                "--results", str(root / "results.tsv"), "--log", str(root / "benchmark.log"),
                "--perf", str(root / "perf.csv"), "--variant", "x", "--threads", "2", "--run", "0"
            ], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Expected exactly one srch total", result.stderr)
            self.assertEqual((root / "results.tsv").read_bytes(), header)

    def test_retained_benchmark_output_formats(self):
        fixtures = Path(__file__).resolve().parent / "fixtures"
        cases = (
            ("ascylib_efrb", "ascylib", 21185700, "21186000"),
            ("ascylib_dvy", "ascylib", 47885860, "47886000"),
            ("ascylib_hj", "ascylib", 33489914, "33490000"),
            ("tpcc_bcco", "tpcc", 198746, "77713.614838"),
            ("tpcc_efrb", "tpcc", 199058, "9422.050814"),
        )
        for name, kind, expected_count, expected_throughput in cases:
            path = fixtures / (name + ".txt")
            with self.subTest(name=name):
                count, throughput, _ = parse_benchmark(path.read_text(), kind)
                self.assertEqual(count, expected_count)
                self.assertEqual(float(throughput), float(expected_throughput))

    @unittest.skipIf(os.name == "nt", "Shell integration runs on Linux")
    def test_shell_driver_with_disabled_and_fixture_perf(self):
        # Temporary fake perf isolates reporting from hardware availability.
        # This is a parser/integration check, not measured performance evidence.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "benchmark.log").write_text(ASCY)
            (root / "fixture.csv").write_text(PERF)
            (root / "perf").write_text('''#!/usr/bin/env bash
set -eu
out=""
while [[ "$1" != -- ]]; do
    if [[ "$1" == -o ]]; then out="$2"; shift; fi
    shift
done
shift
cp "$FAKE_PERF_INPUT" "$out"
"$@"
''')
            (root / "perf").chmod(0o755)
            script = '''set -euo pipefail
source "$1"
perfbench_init_results "$2/results.tsv"
PERFBENCH_PERF=off perfbench_run_rep "$2/results.tsv" "$2/runs" disabled 2 0 ascylib -- cat "$2/benchmark.log"
PERFBENCH_PERF=on perfbench_run_rep "$2/results.tsv" "$2/runs" fixture 2 0 ascylib -- cat "$2/benchmark.log"
perfbench_print_summary "$2/results.tsv" "Normalization test" "$2/summary.txt"
'''
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
                       FAKE_PERF_INPUT=str(root / "fixture.csv"))
            result = subprocess.run(["bash", "-c", script, "check",
                                     str(ARTIFACT / "lib/perfstat_common.sh"), str(root)],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with (root / "results.tsv").open() as f:
                reader = csv.DictReader(f, delimiter="\t")
                self.assertEqual(reader.fieldnames, FIELDS)
                rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["cache_misses_per_op"], "NA")
            self.assertEqual(float(rows[1]["cache_misses_per_op"]), 2)
            self.assertEqual(rows[1]["operation_count"], "300000")
            self.assertIn("*_per_op divide by operation_count", (root / "summary.txt").read_text())


if __name__ == "__main__":
    unittest.main()
