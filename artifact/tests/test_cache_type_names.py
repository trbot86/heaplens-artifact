"""Long header-template names must not widen every allocation's type string."""
import sys
from pathlib import Path
import tracemalloc
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sifter_vis_d3/server'))
from sampler import normalized_type_names


class CacheTypeNames(unittest.TestCase):
    def test_matches_previous_normalization(self):
        names=np.array(['unsigned long', 'node_t<unsigned long, itemid_t*>',
                        'Node< A < B > >', 'plain', 'node_t<unsigned long, itemid_t*>'],dtype=object)
        expected=np.char.replace(names.astype(str),' ','').tolist()
        self.assertEqual(normalized_type_names(names).tolist(),expected)

    def test_one_long_type_does_not_pad_all_rows(self):
        names=np.empty(100000,dtype=object);names[:]='char'
        names[-1]='nested< '+('Template< unsigned long >, '*150)+'end >'
        tracemalloc.start()
        result=normalized_type_names(names)
        _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        self.assertLess(peak,4*1024*1024)
        self.assertEqual(result.dtype,object)
        self.assertEqual(result[-1],names[-1].replace(' ',''))
        self.assertTrue(all(name is result[0] for name in result[:-1]))
