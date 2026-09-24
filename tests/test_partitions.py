import copy
import itertools
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import checker
import interval_checker
from producer import produce
from cases import controls

class PartitionTests(unittest.TestCase):
    def test_every_four_gas_partition(self):
        p=controls()[0]; p['gas']=4; c,_=produce(p)
        for bits in itertools.product([0,1],repeat=4):
            z=copy.deepcopy(c)
            for row in z['bounds']:
                vals={g:v for lo,hi,v in row[3] for g in range(lo,hi+1)}
                chunks=[]; start=0
                for g in range(1,6):
                    if g==5 or bits[g-1] or vals[g]!=vals[start]:
                        chunks.append([start,g-1,vals[start]]); start=g
                row[3]=chunks
            a=checker.check(p,z); b=interval_checker.check(p,z)
            self.assertEqual((a['status'],a['lower'],a['upper']),(b['status'],b['lower'],b['upper']))
    def test_interior_violation_not_only_endpoints(self):
        p=controls()[0]; p['gas']=4; c,_=produce(p)
        for row in c['bounds']:
            if row[:3]==[0,0,2]: row[3]=[[0,1,0],[2,2,9],[3,4,0]]
        for module in [checker,interval_checker]:
            with self.assertRaises(module.Reject): module.check(p,c)
    def test_arbitrary_lower_bound_nonmonotone_allowed(self):
        p=controls()[0]; p['gas']=4
        p['edges'][0]['cost']=1; p['edges'][1]['cost']=2; c,_=produce(p)
        for row in c['bounds']:
            if row[:3]==[0,0,2]: row[3]=[[0,0,0],[1,1,1],[2,4,0]]
        for module in [checker,interval_checker]: self.assertEqual(module.check(p,c)['status'],'gap_bounded')

    def test_semantic_lower_bound_need_not_be_locally_closed(self):
        # B(start,g=1)=1 is a true suffix bound, but the incumbent-0 clipped
        # child profile is too weak to justify it via local inequalities.
        p=controls()[0]; p['gas']=4; c,_=produce(p)
        for row in c['bounds']:
            if row[:3]==[0,0,2]: row[3]=[[0,0,0],[1,1,1],[2,4,0]]
        for module in [checker,interval_checker]:
            with self.assertRaises(module.Reject): module.check(p,c)
