"""Separately implemented forward trace oracle for well-formed test inputs.

No lower-bound table, state dominance, memoization, branch-and-bound or producer
semantics is reused. It enumerates every budget-feasible first-error prefix.
It is not a production parser; malformed-input tests belong to the checker.
"""
from __future__ import annotations
import time
from typing import Any


def enumerate_traces(p: dict[str, Any], max_prefixes: int=200_000,
                     seconds: float=180.0) -> dict[str, Any]:
    began=time.process_time()
    domain=2**p['bits']; best=None; winning=None; count=0; errors=0
    stack=[(p['start'],x,0,0,[],[x],0) for x in p['initial']]
    while stack:
        q,x,used_g,used_h,trace,values,cost=stack.pop()
        count+=1
        if count>max_prefixes or (count%128==0 and time.process_time()-began>seconds):
            return {'status':'unknown','cost':None,'prefixes':count-1,'error_traces':errors}
        if q in p['errors']:
            errors+=1
            if best is None or cost<best:
                best=cost; winning={'initial':values[0],'edges':trace,'values':values,'cost':cost}
            continue
        if used_h==p['steps']:
            continue
        for e in p['edges']:
            if e['src']!=q or x<e['guard'][0] or x>e['guard'][1] or used_g+e['gas']>p['gas']:
                continue
            # Explicit membership test, rather than using producer successors.
            for y in range(domain):
                if e['update']!='havoc':
                    raw=e['update'][0]*x+e['update'][1]
                    if (raw-y)%domain!=0:
                        continue
                stack.append((e['dst'],y,used_g+e['gas'],used_h+1,
                              trace+[e['id']],values+[y],cost+e['cost']))
    return {'status':'safe_bounded' if best is None else 'optimal_bounded',
            'cost':best,'witness':winning,'prefixes':count,'error_traces':errors}
