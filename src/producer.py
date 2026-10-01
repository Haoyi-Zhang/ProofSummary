"""Bounded exact reference producer; not an implementation of GPS.

Witness search is guided by a control-only overapproximate suffix relaxation.
The lower-bound certificate is a separate exact finite recurrence, clipped to
an incumbent when present. It is explicitly a baseline, not a novelty claim.
"""
from __future__ import annotations
import argparse
import heapq
import itertools
import json
import math
from pathlib import Path
from typing import Any
from model import Budget, Exhausted, Unsupported, load, successors, validate

INF=math.inf


def relaxation(p: dict[str, Any], budget: Budget) -> dict[tuple[str,int,int], float|int]:
    budget.check_time()
    a={}
    for h in range(p['steps']+1):
        for g in range(p['gas']+1):
            for q in p['locations']:
                if q in p['errors']:
                    a[q,g,h]=0
                elif h==0:
                    a[q,g,h]=INF
                else:
                    vals=[]
                    for e in p['edges']:
                        if e['src']==q and e['gas']<=g:
                            budget.tick()
                            vals.append(e['cost']+a[e['dst'],g-e['gas'],h-1])
                    a[q,g,h]=min(vals,default=INF)
                    budget.check_time()
    budget.check_time()
    return a


def search(p: dict[str, Any], guided: bool=True, *, limit: int=200_000) -> tuple[dict[str,Any]|None, dict[str,int]]:
    validate(p)
    bound=Budget(limit)
    a=relaxation(p,bound) if guided else None
    guide_work=bound.work
    steps=p['steps']; gas=p['gas']; serial=itertools.count()
    frontier=[]; dist={}; parent={}
    for x in p['initial']:
        key=(p['start'],x,gas,steps)
        dist[key]=0; parent[key]=None
        low=a[p['start'],gas,steps] if a is not None else 0
        if low<INF:
            heapq.heappush(frontier,(low,0,next(serial),key))
    expanded=0
    while frontier:
        bound.check_time()
        _,cost,_,key=heapq.heappop(frontier)
        if dist.get(key)!=cost:
            continue
        bound.tick(); expanded+=1
        q,x,g,h=key
        if q in p['errors']:
            states=[]; edges=[]; cur=key
            while True:
                states.append(cur[1])
                par=parent[cur]
                if par is None:
                    break
                prev,eid=par; edges.append(eid); cur=prev
            states.reverse(); edges.reverse()
            bound.check_time()
            return {'initial':states[0],'edges':edges,'values':states,'cost':cost},{'expanded':expanded,'relaxation_obligations':guide_work,'work':bound.work}
        if h==0:
            continue
        for e,y in successors(p,q,x):
            bound.tick()
            if e['gas']>g:
                continue
            nk=(e['dst'],y,g-e['gas'],h-1); nc=cost+e['cost']
            if nc>=dist.get(nk,INF):
                continue
            heuristic=a[nk[0],nk[2],nk[3]] if a is not None else 0
            if heuristic==INF:
                continue
            dist[nk]=nc; parent[nk]=(key,e['id'])
            heapq.heappush(frontier,(nc+heuristic,nc,next(serial),nk))
    bound.check_time()
    return None,{'expanded':expanded,'relaxation_obligations':guide_work,'work':bound.work}


def suffixes(p: dict[str, Any], budget: Budget) -> dict[tuple[str,int,int,int],int|float]:
    budget.check_time()
    b={}
    for h in range(p['steps']+1):
        for g in range(p['gas']+1):
            for q in p['locations']:
                for x in range(1<<p['bits']):
                    key=(q,x,g,h)
                    if q in p['errors']:
                        b[key]=0
                    elif h==0:
                        b[key]=INF
                    else:
                        best=INF
                        for e,y in successors(p,q,x):
                            if e['gas']<=g:
                                budget.tick()
                                best=min(best,e['cost']+b[e['dst'],y,g-e['gas'],h-1])
                        b[key]=best
                    budget.check_time()
    budget.check_time()
    return b


def produce(p: dict[str, Any]) -> tuple[dict[str,Any],dict[str,Any]]:
    validate(p)
    w,stats=search(p)
    budget=Budget()
    b=suffixes(p,budget)
    clip=w['cost'] if w is not None else INF
    rows=[]; segments=0
    for qi,q in enumerate(p['locations']):
        for x in range(1<<p['bits']):
            for h in range(p['steps']+1):
                vals=[min(b[q,x,g,h],clip) for g in range(p['gas']+1)]
                ranges=[]; start=0
                for g in range(1,p['gas']+2):
                    if g==p['gas']+1 or vals[g]!=vals[start]:
                        val=None if vals[start]==INF else vals[start]
                        ranges.append([start,g-1,val]); start=g
                segments+=len(ranges); rows.append([qi,x,h,ranges])
    budget.check_time()
    stats.update({'cells':len(b),'segments':segments,'suffix_obligations':budget.work})
    cert={'query':p,'witness':w,'bounds':rows}
    return cert,stats


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input'); ap.add_argument('output')
    args=ap.parse_args()
    try:
        cert,stats=produce(load(args.input))
        Path(args.output).write_text(json.dumps(cert,separators=(',',':'))+'\n')
        print(json.dumps({'result':'certificate_generated','statistics':stats}))
        return 0
    except (Unsupported,Exhausted,OSError,ValueError,KeyError,TypeError,RecursionError) as e:
        print(json.dumps({'result':'unknown','reason':str(e)}))
        return 2

if __name__=='__main__':
    raise SystemExit(main())
