"""Replay retained public-source quotient inputs without regenerating them."""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from frontier_checker import check
from frontier_oracle import enumerate_frontier
from frontier_producer import produce


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--source',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
    if a.out.exists(): raise SystemExit('output directory must not exist')
    for d in ('inputs','certificates','details'): (a.out/d).mkdir(parents=True,exist_ok=False)
    with (a.source/'raw.csv').open(newline='') as f: selected=list(csv.DictReader(f))
    fields=selected[0].keys(); rows=[]
    with (a.out/'raw.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for old in selected:
            p=json.loads((a.source/'inputs'/(old['id']+'.json')).read_text()); cert,stats=produce(p); checked=check(p,cert); oracle=enumerate_frontier(p)
            expected=old['expected_safe']=='true'; agree=(checked['status']=='safe_bounded')==expected and checked['status']==oracle['status'] and checked['initial_frontier']==oracle['frontier']
            row={'id':p['id'],'source':old['source'],'expected_safe':old['expected_safe'],'status':checked['status'],'cost':'' if checked['upper'] is None else checked['upper'],
                 'frontier':json.dumps(checked['initial_frontier'],separators=(',',':')),'oracle_status':oracle['status'],'agreement':'yes' if agree else 'NO'}
            rows.append(row); w.writerow(row)
            (a.out/'inputs'/(p['id']+'.json')).write_text(json.dumps(p,sort_keys=True)+'\n')
            (a.out/'certificates'/(p['id']+'.json')).write_text(json.dumps(cert,separators=(',',':'))+'\n')
            (a.out/'details'/(p['id']+'.json')).write_text(json.dumps({'checker':checked,'oracle':oracle,'producer_statistics':stats,'source':old['source'],'expected_safe':expected},sort_keys=True)+'\n')
    s={'cases':len(rows),'agreement':sum(r['agreement']=='yes' for r in rows),'safe':sum(r['status']=='safe_bounded' for r in rows),'unsafe':sum(r['status']=='optimal_bounded' for r in rows)}
    (a.out/'summary.json').write_text(json.dumps(s,indent=2,sort_keys=True)+'\n'); print(json.dumps(s,sort_keys=True)); return 0 if s['agreement']==s['cases'] else 1
if __name__=='__main__': raise SystemExit(main())
