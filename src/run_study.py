"""Reproduce fixed small-case experiments, with raw per-case evidence.

Single worker; each bounded case is independently timed. No network, solver,
GPU, external model, or shared search routine in the exhaustive oracle.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import resource
import sys
import time
from cases import controls, generated, family
from producer import produce, search
from checker import check, Limit, Reject
from interval_checker import check as check_intervals
from oracle import enumerate_traces
from model import Unsupported, Exhausted
from bad_search import search_erased

FIELDS=['id','group','bits','locations','edges','gas','steps','cells','status','cost',
        'oracle_status','oracle_cost','oracle_prefixes','error_traces','segments',
        'certificate_bytes','guided_expanded','ucs_expanded','guide_work','suffix_work',
        'checker_work','interval_work','interval_cpu_s','producer_cpu_s','checker_cpu_s','oracle_cpu_s','ucs_cpu_s','peak_rss_kib','agreement']

def run_one(p,group,out):
    r={k:'' for k in FIELDS}; r.update(id=p['id'],group=group,bits=p['bits'],
        locations=len(p['locations']),edges=len(p['edges']),gas=p['gas'],steps=p['steps'])
    inp=out/'inputs'/ (p['id']+'.json'); inp.write_text(json.dumps(p,sort_keys=True)+'\n')
    t=time.process_time()
    try:
        c,s=produce(p); r['producer_cpu_s']=time.process_time()-t
        text=json.dumps(c,separators=(',',':')); (out/'certificates'/(p['id']+'.json')).write_text(text+'\n')
        r['certificate_bytes']=len((text+'\n').encode()); r.update(cells=s['cells'],segments=s['segments'],
            guided_expanded=s['expanded'],guide_work=s['relaxation_obligations'],suffix_work=s['suffix_obligations'])
        t=time.process_time(); k=check(p,c); r['checker_cpu_s']=time.process_time()-t
        r.update(status=k['status'],cost=k['upper'],checker_work=k['transition_obligations'])
        t=time.process_time(); ik=check_intervals(p,c); r['interval_cpu_s']=time.process_time()-t
        r['interval_work']=ik['interval_obligations']
        if (k['status'],k['lower'],k['upper'])!=(ik['status'],ik['lower'],ik['upper']):
            raise Reject('DENSE/INTERVAL SCIENTIFIC MISMATCH')
    except (Exhausted,Unsupported,Limit) as e:
        r.update(status='unknown',agreement='incomplete'); (out/'details'/(p['id']+'.json')).write_text(json.dumps({'exception':str(e)})+'\n')
        return r
    t=time.process_time(); o=enumerate_traces(p); r['oracle_cpu_s']=time.process_time()-t
    r.update(oracle_status=o['status'],oracle_cost=o['cost'],oracle_prefixes=o['prefixes'],error_traces=o['error_traces'])
    t=time.process_time()
    try:
        w,us=search(p,guided=False); r['ucs_cpu_s']=time.process_time()-t; r['ucs_expanded']=us['expanded']
        ucost=None if w is None else w['cost']
        same=o['status']!='unknown' and (k['status'],k['upper'])==(o['status'],o['cost']) and ucost==k['upper']
        r['agreement']='yes' if same else ('incomplete' if o['status']=='unknown' else 'NO')
    except Exhausted:
        r['agreement']='incomplete'
    details={'checker':k,'interval_checker':ik,'producer_statistics':s,'oracle':o}
    if p['id'] in ['gas-erasure','step-erasure','value-erasure']:
        erase={'gas-erasure':'gas','step-erasure':'steps','value-erasure':'value'}[p['id']]
        details['intentionally_unsound_ablation']={'erased':erase,'returned_cost':search_erased(p,erase)}
    (out/'details'/(p['id']+'.json')).write_text(json.dumps(details,sort_keys=True)+'\n')
    r['peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    for k in FIELDS:
        if k.endswith('_cpu_s') and isinstance(r[k],float): r[k]=format(r[k],'.9f')
    return r

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--phase',choices=['pilot','main','family','boundary'],required=True)
    ap.add_argument('--out',type=Path,required=True); args=ap.parse_args()
    if args.out.exists(): raise SystemExit('Output directory must not exist; use a new empty destination.')
    for d in ['inputs','certificates','details']: (args.out/d).mkdir(parents=True,exist_ok=False)
    if args.phase=='pilot': cases=[(p,'hand-control') for p in controls()]+[(generated(i),'pilot-generated') for i in range(24)]
    elif args.phase=='main': cases=[(generated(i),'main-generated') for i in range(24,300)]
    elif args.phase=='family': cases=[(p,'finite-family') for p in family()]
    else:
        cases=[]
        for G in [0,1,4,16,32,64,96,128]:
            for H in [8,16,32,64]:
                p=family()[6]; p.update(id=f'boundary-g{G}-h{H}',gas=G,steps=H)
                cases.append((p,'resource-boundary'))
    t=time.process_time(); rows=[]
    with (args.out/'raw.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS); writer.writeheader()
        for p,group in cases:
            r=run_one(p,group,args.out); rows.append(r); writer.writerow(r); f.flush()
            if r['agreement']=='NO': raise SystemExit('SCIENTIFIC MISMATCH: '+p['id'])
    summary={'phase':args.phase,'cases':len(rows),'agreement':sum(r['agreement']=='yes' for r in rows),
        'incomplete':sum(r['agreement']=='incomplete' for r in rows),'cpu_seconds':time.process_time()-t,
        'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1}
    (args.out/'summary.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n'); print(json.dumps(summary))
    return 0 if summary['agreement']==len(rows) else 2
if __name__=='__main__': raise SystemExit(main())
