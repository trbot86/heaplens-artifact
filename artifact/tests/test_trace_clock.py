import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sifter_vis_d3/server'))
from trace_clock import clock_path, read_clock, validate_timestamp_hz


class TraceClockTests(unittest.TestCase):
    def test_per_input_unknown_and_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            a,b = Path(td)/'a.sqlite',Path(td)/'b.sqlite'
            self.assertEqual(read_clock(a)['display_unit'],'ticks')
            clock_path(a).write_text(json.dumps({'timestamp_hz':2200000000,'source':'capture'}))
            self.assertEqual(read_clock(a)['timestamp_hz'],2200000000)
            self.assertIsNone(read_clock(b)['timestamp_hz'])
    def test_invalid_clock_is_never_assumed(self):
        for hz in (0,-1,float('inf'),float('nan'),True,None,'unknown'):
            with self.assertRaises(ValueError): validate_timestamp_hz(hz)


if __name__=='__main__':unittest.main()
