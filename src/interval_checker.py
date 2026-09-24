"""Gas-interval checker for finite resource-indexed lower-bound certificates.

Trust boundary: Python, JSON parsing, the externally supplied mathematical CFG,
and this file. No imports from the producer, model, search or oracle. Parser/replay
logic is intentionally adapted from the dense checker, not an independent replica.
This is executable finite checking, not a machine-checked proof of this implementation.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import time
from typing import Any

class Reject(ValueError):
    pass

class Limit(RuntimeError):
    pass


def nat(v: Any, high: int=10**12) -> bool:
    return type(v) is int and 0<=v<=high


def require(ok: bool, why: str) -> None:
    if not ok:
        raise Reject(why)


def decode(path: str) -> Any:
    with Path(path).open('rb') as stream:
        raw=stream.read(8*1024*1024+1)
    if len(raw)>8*1024*1024:
        raise Limit('file byte cap')
    def object_pairs(pairs: list[tuple[str,Any]]) -> dict[str,Any]:
        out={}
        for k,v in pairs:
            require(k not in out,'duplicate JSON key')
            out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=object_pairs)


def check(p: Any, cert: Any, *, max_work: int=200_000, seconds: float=180.0) -> dict[str, Any]:
    start_cpu=time.process_time()
    require(type(p) is dict and set(p)=={'id','bits','locations','start','initial','errors','gas','steps','edges'},'input fields')
    require(type(p['id']) is str and 0<len(p['id'])<=80,'input identifier')
    require(nat(p['bits'],6) and p['bits']>=1,'bit width')
    require(nat(p['gas'],128) and nat(p['steps'],128),'query bounds')
    locations=p['locations']; width=1<<p['bits']; G=p['gas']; H=p['steps']
    require(type(locations) is list and 0<len(locations)<=128 and all(type(q) is str and 0<len(q)<=40 for q in locations),'locations')
    require(len(set(locations))==len(locations),'duplicate locations')
    require(type(p['start']) is str and p['start'] in locations,'start location')
    for name in ['initial','errors']:
        require(type(p[name]) is list and len(p[name])>0,name)
    require(all(nat(x,width-1) for x in p['initial']) and len(set(p['initial']))==len(p['initial']),'initial valuations')
    require(all(type(q) is str and q in locations for q in p['errors']) and len(set(p['errors']))==len(p['errors']),'error locations')
    cells=len(locations)*width*(G+1)*(H+1)
    if cells>200_000:
        raise Limit('product state cap')
    require(type(p['edges']) is list and len(p['edges'])<=512,'edges')
    edges={}; outgoing={q:[] for q in locations}
    for e in p['edges']:
        require(type(e) is dict and set(e)=={'id','src','dst','guard','update','gas','cost'},'edge fields')
        require(nat(e['id'],1_000_000) and e['id'] not in edges,'edge identifier')
        require(type(e['src']) is str and type(e['dst']) is str and e['src'] in outgoing and e['dst'] in outgoing,'edge endpoints')
        require(nat(e['cost'],1_000_000) and nat(e['gas'],1),'edge resources')
        a=e['guard']; u=e['update']
        require(type(a) is list and len(a)==2 and all(nat(v,width-1) for v in a) and a[0]<=a[1],'interval guard')
        if u!='havoc':
            require(type(u) is list and len(u)==2 and all(type(v) is int and -2**31<=v<2**31 for v in u),'affine update')
        edges[e['id']]=e; outgoing[e['src']].append(e)
    require(type(cert) is dict and set(cert)=={'query','witness','bounds'},'certificate fields')
    # Structural equality binds the certificate to the externally selected query.
    # It does not rely on a producer-supplied filename, identifier or digest.
    require(cert['query']==p,'certificate/query mismatch')
    w=cert['witness']; upper=None
    if w is not None:
        require(type(w) is dict and set(w)=={'initial','edges','values','cost'},'witness fields')
        require(nat(w['initial'],width-1) and w['initial'] in p['initial'],'witness initial value')
        require(type(w['edges']) is list and len(w['edges'])<=H,'witness length')
        require(type(w['values']) is list and len(w['values'])==len(w['edges'])+1 and all(nat(x,width-1) for x in w['values']),'witness valuations')
        require(w['values'][0]==w['initial'],'witness initial valuation mismatch')
        require(nat(w['cost']),'witness cost type')
        q=p['start']; x=w['initial']; spent=0; paid=0
        for i,eid in enumerate(w['edges']):
            require(nat(eid,1_000_000) and eid in edges,'unknown witness edge')
            e=edges[eid]; y=w['values'][i+1]
            require(q not in p['errors'],'witness continues after first error')
            require(e['src']==q and e['guard'][0]<=x<=e['guard'][1],'disabled witness edge')
            u=e['update']
            require(u=='havoc' or y==(u[0]*x+u[1])%width,'witness update')
            spent+=e['gas']; paid+=e['cost']
            require(spent<=G,'witness gas exhaustion')
            q=e['dst']; x=y
        require(q in p['errors'],'witness does not reach error')
        require(paid==w['cost'],'witness cost mismatch')
        upper=paid
    rows=cert['bounds']
    require(type(rows) is list and len(rows)==len(locations)*width*(H+1),'missing or extra bound rows')
    profiles={}; seen=set(); segment_count=0
    for row in rows:
        require(type(row) is list and len(row)==4,'bound row format')
        qi,x,h,segments=row
        require(nat(qi,len(locations)-1) and nat(x,width-1) and nat(h,H),'bound row index')
        index=(qi,x,h)
        require(index not in seen,'duplicate bound row'); seen.add(index)
        require(type(segments) is list and 1<=len(segments)<=G+1,'segments')
        expected=0; profile=[]
        for segment in segments:
            require(type(segment) is list and len(segment)==3,'segment format')
            lo,hi,value=segment
            require(nat(lo,G) and nat(hi,G) and lo==expected and hi>=lo,'non-partitioning gas intervals')
            require(value is None or nat(value),'bound value')
            value=math.inf if value is None else value
            profile.append((lo,hi,value))
            expected=hi+1; segment_count+=1
        require(expected==G+1,'uncovered gas budget')
        profiles[locations[qi],x,h]=tuple(profile)
    require(len(profiles)==len(locations)*width*(H+1),'incomplete bound domain')
    obligations=0
    for (q,x,h),left in profiles.items():
        if q in p['errors']:
            require(all(v==0 for _,_,v in left),'nonzero lower bound at error')
        elif h>0:
            for e in outgoing[q]:
                if not (e['guard'][0]<=x<=e['guard'][1]) or e['gas']>G:
                    continue
                u=e['update']; d=e['gas']
                ys=range(width) if u=='havoc' else ((u[0]*x+u[1])%width,)
                for y in ys:
                    right=profiles[e['dst'],y,h-1]
                    i=0; j=0; covered=0
                    while i<len(left) and j<len(right):
                        a,b,lhs=left[i]; c,f,rhs=right[j]
                        # A target interval [c,f] applies to source gas [c+d,f+d].
                        lo=max(a,c+d,d); hi=min(b,f+d,G)
                        if lo<=hi:
                            obligations+=1; covered+=hi-lo+1
                            if obligations>max_work:
                                raise Limit('interval obligation cap')
                            if obligations%128==0 and time.process_time()-start_cpu>seconds:
                                raise Limit('CPU cap')
                            require(lhs<=e['cost']+rhs,'invalid local lower-bound inequality')
                        if b<f+d: i+=1
                        elif b>f+d: j+=1
                        else: i+=1; j+=1
                    require(covered==G-d+1,'internal shifted-interval coverage failure')
    lower=min(profiles[p['start'],x,H][-1][2] for x in p['initial'])
    if lower==math.inf:
        require(upper is None,'finite witness contradicts infinite lower bound')
        status='safe_bounded'
    elif upper is None:
        status='unknown'
    else:
        require(lower<=upper,'bounds contradict witnessed cost')
        status='optimal_bounded' if lower==upper else 'gap_bounded'
    return {'status':status,'lower':None if lower==math.inf else lower,'upper':upper,
            'gas':G,'steps':H,'cells':cells,'segments':segment_count,
            'interval_obligations':obligations}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input'); parser.add_argument('certificate')
    args=parser.parse_args()
    try:
        result=check(decode(args.input),decode(args.certificate))
        print(json.dumps(result,sort_keys=True))
        return 0 if result['status'] in {'optimal_bounded','safe_bounded','gap_bounded'} else 2
    except Limit as e:
        print(json.dumps({'status':'unknown','reason':str(e)})); return 2
    except (Reject,ValueError,OSError,TypeError,KeyError,IndexError,RecursionError) as e:
        print(json.dumps({'status':'rejected','reason':str(e)})); return 1

if __name__=='__main__':
    raise SystemExit(main())
