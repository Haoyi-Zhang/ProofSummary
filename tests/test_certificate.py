"""Independent obligations, malformed inputs and discriminating negative controls."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import checker
import model
import producer as producer_module
from producer import produce, search
from model import Unsupported, Exhausted
from cases import controls
from bad_search import search_erased
from oracle import enumerate_traces


class _CountingClock:
    def __init__(self, expire_on=None):
        self.calls=0; self.expire_on=expire_on
    def __call__(self):
        self.calls+=1
        return 1000.0+float(self.calls-self.expire_on) if self.expire_on is not None and self.calls>=self.expire_on else 0.0

class CertificateTests(unittest.TestCase):
    def setUp(self):
        self.p=controls()[0]; self.c,_=produce(self.p)
    def reject(self,c,p=None):
        with self.assertRaises(checker.Reject): checker.check(self.p if p is None else p,c)
    def test_control_agreement(self):
        for p in controls():
            c,_=produce(p); k=checker.check(p,c); o=enumerate_traces(p)
            self.assertEqual(k['status'],o['status'],p['id']); self.assertEqual(k['upper'],o['cost'])
    def test_erased_gas_is_wrong(self):
        self.assertEqual(search_erased(self.p,'gas'),9); self.assertEqual(enumerate_traces(self.p)['cost'],1)
    def test_erased_steps_is_wrong(self):
        p=controls()[1]; self.assertEqual(search_erased(p,'steps'),9); self.assertEqual(enumerate_traces(p)['cost'],1)
    def test_erased_value_is_wrong(self):
        p=controls()[2]; self.assertEqual(search_erased(p,'value'),9); self.assertEqual(enumerate_traces(p)['cost'],1)
    def test_valid_nonminimal_is_gap(self):
        c=copy.deepcopy(self.c); c['witness']={'initial':0,'edges':[3],'values':[0,0],'cost':9}
        k=checker.check(self.p,c); self.assertEqual((k['status'],k['lower'],k['upper']),('gap_bounded',1,9))
    def test_replay_only_has_no_minimality(self):
        c=copy.deepcopy(self.c); c['witness']={'initial':0,'edges':[3],'values':[0,0],'cost':9}
        for row in c['bounds']: row[3]=[[0,self.p['gas'],0]]
        self.assertEqual(checker.check(self.p,c)['status'],'gap_bounded')
    def test_missing_row(self):
        c=copy.deepcopy(self.c); c['bounds'].pop(); self.reject(c)
    def test_duplicate_row(self):
        c=copy.deepcopy(self.c); c['bounds'][-1]=c['bounds'][0]; self.reject(c)
    def test_missing_gas_cell(self):
        c=copy.deepcopy(self.c); c['bounds'][0][3]=[[0,0,0]]; self.reject(c)
    def test_overlapping_gas_segments(self):
        c=copy.deepcopy(self.c); c['bounds'][0][3]=[[0,1,0],[1,1,0]]; self.reject(c)
    def test_wrong_target_bound(self):
        c=copy.deepcopy(self.c)
        for row in c['bounds']:
            if row[0]==2: row[3]=[[0,1,1]]
        self.reject(c)
    def test_overstated_start_bound(self):
        c=copy.deepcopy(self.c)
        for row in c['bounds']:
            if row[:3]==[0,0,2]: row[3]=[[0,1,9]]
        self.reject(c)
    def test_wrong_witness_cost(self):
        c=copy.deepcopy(self.c); c['witness']['cost']+=1; self.reject(c)
    def test_wrong_update(self):
        c=copy.deepcopy(self.c); c['witness']['values'][1]=1; self.reject(c)
    def test_unknown_edge(self):
        c=copy.deepcopy(self.c); c['witness']['edges'][0]=999; self.reject(c)
    def test_bound_binding(self):
        p=copy.deepcopy(self.p); p['gas']=2; self.reject(self.c,p)
    def test_program_binding(self):
        p=copy.deepcopy(self.p); p['edges'][0]['cost']=2; self.reject(self.c,p)
    def test_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'x.json'; f.write_text('{"gas":1,"gas":2}')
            with self.assertRaises(checker.Reject): checker.decode(str(f))
    def test_bool_is_not_integer(self):
        c=copy.deepcopy(self.c); c['bounds'][0][3][0][2]=True; self.reject(c)
    def test_float_is_not_integer(self):
        c=copy.deepcopy(self.c); c['bounds'][0][3][0][2]=1.0; self.reject(c)
    def test_query_binding_rejects_bool_in_certificate_bytes(self):
        c=copy.deepcopy(self.c); c['query']['bits']=True
        qb=json.dumps(self.p,separators=(',',':')).encode()
        cb=json.dumps(c,separators=(',',':')).encode()
        with self.assertRaises(checker.Reject): checker.check_bytes(qb,cb)
    def test_query_binding_rejects_equal_float_in_certificate_bytes(self):
        c=copy.deepcopy(self.c); c['query']['gas']=float(self.p['gas'])
        qb=json.dumps(self.p,separators=(',',':')).encode()
        cb=json.dumps(c,separators=(',',':')).encode()
        with self.assertRaises(checker.Reject): checker.check_bytes(qb,cb)
    def test_dense_producer_deadline_checked_before_zero_candidate_return(self):
        p={'id':'zero-dense-clock','bits':1,'locations':['s','z'],'start':'s','initial':[0],
           'errors':['z'],'gas':0,'steps':1,'edges':[]}
        counter=_CountingClock()
        with patch.object(model.time,'process_time',counter):
            producer_module.produce(p)
        expiring=_CountingClock(counter.calls)
        with patch.object(model.time,'process_time',expiring):
            with self.assertRaises(model.Exhausted): producer_module.produce(p)
    def test_dense_checker_deadline_checked_before_sub128_return(self):
        baseline=checker.check(self.p,self.c)
        self.assertLess(baseline['transition_obligations'],128)
        counter=_CountingClock()
        with patch.object(checker.time,'process_time',counter): checker.check(self.p,self.c,seconds=.5)
        expiring=_CountingClock(counter.calls)
        with patch.object(checker.time,'process_time',expiring):
            with self.assertRaises(checker.Limit): checker.check(self.p,self.c,seconds=.5)
    def test_no_witness_with_weak_bound_unknown(self):
        c=copy.deepcopy(self.c); c['witness']=None
        self.assertEqual(checker.check(self.p,c)['status'],'unknown')
    def test_checker_work_cap_unknown(self):
        with self.assertRaises(checker.Limit): checker.check(self.p,self.c,max_work=0)
    def test_oracle_work_cap_unknown(self):
        self.assertEqual(enumerate_traces(self.p,max_prefixes=1)['status'],'unknown')
    def test_search_cap_unknown(self):
        with self.assertRaises(Exhausted): search(self.p,limit=0)
    def test_product_cap(self):
        p=copy.deepcopy(self.p); p.update(bits=6,gas=128,steps=128)
        with self.assertRaises(checker.Limit): checker.check(p,{})
        with self.assertRaises(Unsupported): produce(p)
    def test_havoc_forged_infinity(self):
        p=controls()[4]; c,_=produce(p)
        for row in c['bounds']:
            if row[:3]==[0,0,2]: row[3]=[[0,0,None]]
        self.reject(c,p)
    def test_zero_cycle_forged_safety(self):
        p=controls()[3]; c,_=produce(p); c['witness']=None
        for row in c['bounds']:
            if row[0]!=2: row[3]=[[0,0,None]]
        self.reject(c,p)
    def test_no_continuing_after_error(self):
        p=controls()[7]; p['steps']=2
        p['edges']=[{'id':0,'src':'z','dst':'z','guard':[0,1],'update':[1,0],'gas':0,'cost':0}]
        c,_=produce(p); c['witness']['edges']=[0]; c['witness']['values']=[0,0]
        self.reject(c,p)
    def test_all_initial_states_needed(self):
        p=controls()[8]; c,_=produce(p)
        c['witness']={'initial':0,'edges':[0],'values':[0,0],'cost':7}
        self.assertEqual(checker.check(p,c)['status'],'gap_bounded')

if __name__=='__main__': unittest.main()
