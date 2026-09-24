"""Deterministic, self-contained mathematical controls; not public C benchmarks."""
from __future__ import annotations
import random
from typing import Any

def edge(i, s, t, *, cost=0, gas=0, update=None, guard=None):
    return {'id':i,'src':s,'dst':t,'cost':cost,'gas':gas,
            'update':[1,0] if update is None else update,
            'guard':[0,1] if guard is None else guard}

def program(name, locations, edges, *, gas=1, steps=2, bits=1, initial=None):
    return {'id':name,'bits':bits,'locations':locations,'start':locations[0],
            'initial':[0] if initial is None else initial,'errors':[locations[-1]],
            'gas':gas,'steps':steps,'edges':edges}

def controls():
    return [
      program('gas-erasure',['s','a','z'],[
        edge(0,'s','a',gas=1),edge(1,'s','a',cost=1),
        edge(2,'a','z',gas=1),edge(3,'s','z',cost=9)]),
      program('step-erasure',['s','u','a','z'],[
        edge(0,'s','u'),edge(1,'u','a'),edge(2,'s','a',cost=1),
        edge(3,'a','z'),edge(4,'s','z',cost=9)],gas=0),
      program('value-erasure',['s','a','z'],[
        edge(0,'s','a',update=[0,0]),edge(1,'s','a',cost=1,update=[0,1]),
        edge(2,'a','z',guard=[1,1]),edge(3,'s','z',cost=9)],gas=0),
      program('zero-cycle',['s','a','z'],[
        edge(0,'s','a'),edge(1,'a','a'),edge(2,'a','z',cost=3)],gas=0,steps=4),
      program('havoc-choice',['s','a','z'],[
        edge(0,'s','a',update='havoc',guard=[0,3]),
        edge(1,'a','z',guard=[3,3],cost=2),
        edge(2,'s','z',guard=[0,3],cost=8)],gas=0,bits=2),
      program('modular-wrap',['s','a','z'],[
        edge(0,'s','a',update=[1,1],guard=[0,3]),
        edge(1,'a','z',guard=[0,0],cost=2)],gas=0,bits=2,initial=[3]),
      program('safe-loop',['s','z'],[edge(0,'s','s')],gas=0,steps=5),
      program('initial-error',['z'],[],gas=0,steps=0),
      program('multiple-initials',['s','z'],[
        edge(0,'s','z',guard=[0,0],cost=7),
        edge(1,'s','z',guard=[1,1],cost=2)],gas=0,steps=1,initial=[0,1]),
    ]

def generated(seed: int):
    r=random.Random(seed); n=r.randint(2,5); bits=r.randint(1,3); width=1<<bits
    qs=['q'+str(i) for i in range(n)]; es=[]
    for i in range(r.randint(n,2*n+3)):
        lo=r.randrange(width); hi=r.randrange(lo,width)
        u='havoc' if r.random()<.13 else [r.choice([-1,0,1,2]),r.randint(-width,width)]
        es.append(edge(i,r.choice(qs[:-1]),r.choice(qs),cost=r.randrange(6),
                       gas=r.randrange(2),update=u,guard=[lo,hi]))
    return program('generated-'+str(seed),qs,es,gas=r.randrange(4),steps=r.randrange(1,6),
                   bits=bits,initial=sorted(r.sample(range(width),r.randint(1,min(width,2)))))

def family():
    # A two-prefix choice whose feasibility and optimum switch with both resources.
    out=[]
    for G in range(4):
      for H in range(5):
        for a in range(4):
          for b in range(4):
            out.append(program(f'family-g{G}-h{H}-a{a}-b{b}', ['s','u','a','z'],[
                edge(0,'s','u',cost=0,gas=1),edge(1,'u','a',cost=0,gas=1),
                edge(2,'s','a',cost=a,gas=0),edge(3,'a','z',cost=b,gas=1),
                edge(4,'s','z',cost=9,gas=0)], gas=G,steps=H))
    return out
