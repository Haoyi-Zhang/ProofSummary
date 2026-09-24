"""Intentionally incorrect dominance ablations, only for owned toy controls.

Never used by the certifying producer. Their wrong outputs are expected tests.
"""
from __future__ import annotations
import heapq
import itertools
from model import successors, validate

def search_erased(p, erase):
    validate(p)
    def key(s):
        q,x,g,h=s
        return {'gas':(q,x,h),'steps':(q,x,g),'value':(q,g,h)}[erase]
    count=itertools.count(); heap=[]; dist={}
    for x in p['initial']:
        s=(p['start'],x,p['gas'],p['steps']); dist[key(s)]=0
        heapq.heappush(heap,(0,next(count),s))
    while heap:
        c,_,s=heapq.heappop(heap)
        if c!=dist.get(key(s)): continue
        q,x,g,h=s
        if q in p['errors']: return c
        if h==0: continue
        for e,y in successors(p,q,x):
            if e['gas']>g: continue
            v=(e['dst'],y,g-e['gas'],h-1); nc=c+e['cost']
            if nc>=dist.get(key(v),float('inf')): continue
            dist[key(v)]=nc; heapq.heappush(heap,(nc,next(count),v))
    return None
