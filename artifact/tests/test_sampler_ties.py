"""Regression for converter-generated retirement at a replacement's timestamp."""
import itertools,json,pathlib,sys,unittest
import pandas as pd
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'sifter_vis_d3/server'))
from sampler import Sampler
def row(ts,new,tp='node_t',addr=4096):
 return dict(file='test.c' if tp!='NULL' else 'NULL',size=64 if new else 0,addr=addr,type=tp,
             ts=ts,is_alloc=int(new),line=1,actualAddr=addr,actualSize=64)
def objects(rows):return Sampler.__new__(Sampler).get_objects(pd.DataFrame(rows)).to_dict('records')
class Ties(unittest.TestCase):
 def test_untyped_to_typed_all_input_orders(self):
  for rows in itertools.permutations([row(10,True,'NULL'),row(20,True),row(20,False,'NULL')]):
   found=objects(rows);self.assertEqual(len(found),1);self.assertTrue(pd.isna(found[0]['freeTs']))
 def test_typed_replacement_all_input_orders(self):
  for rows in itertools.permutations([row(10,True),row(20,True,'info_t'),row(20,False)]):
   found=objects(rows);old=next(x for x in found if x['allocTs']==10);new=next(x for x in found if x['allocTs']==20)
   self.assertEqual(old['freeTs'],20);self.assertTrue(pd.isna(new['freeTs']))
 def test_later_retirement_closes_replacement(self):
  found=objects([row(10,True,'NULL'),row(20,True),row(20,False,'NULL'),row(30,False,'NULL')])
  self.assertEqual(len(found),1);self.assertEqual(found[0]['freeTs'],30)
 def test_distinct_timestamps_and_addresses(self):
  found=objects([row(10,True),row(15,True,addr=8192),row(20,False,'NULL'),row(30,True),row(40,False,'NULL')])
  self.assertEqual([x['freeTs'] for x in found if x['addr']==4096],[20,40])
  self.assertTrue(pd.isna(next(x for x in found if x['addr']==8192)['freeTs']))
if __name__ == '__main__':
 unittest.main()
