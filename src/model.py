"""Finite modular control-flow semantics for the producer only.

The checker and exhaustive oracle deliberately do not import this module.
The input is a mathematical finite transition system, not a C front end.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterator
import json
import time

MAX_CELLS = 200_000
MAX_WORK = 200_000

class Unsupported(ValueError):
    pass

class Exhausted(RuntimeError):
    pass

@dataclass
class Budget:
    limit: int = MAX_WORK
    seconds: float = 180.0
    work: int = 0
    def __post_init__(self) -> None:
        self.started = time.process_time()
    def check_time(self) -> None:
        if time.process_time() - self.started > self.seconds:
            raise Exhausted('CPU limit')
    def tick(self, n: int = 1) -> None:
        self.work += n
        if self.work > self.limit:
            raise Exhausted('candidate/obligation limit')
        self.check_time()


def integer(v: Any, lo: int, hi: int) -> bool:
    return type(v) is int and lo <= v <= hi


def validate(p: dict[str, Any]) -> None:
    keys = {'id', 'bits', 'locations', 'start', 'initial', 'errors', 'gas', 'steps', 'edges'}
    if type(p) is not dict or set(p) != keys:
        raise Unsupported('unsupported input fields')
    if not isinstance(p['id'], str) or not 1 <= len(p['id']) <= 80:
        raise Unsupported('case identifier')
    if not integer(p['bits'], 1, 6) or not integer(p['gas'], 0, 128) or not integer(p['steps'], 0, 128):
        raise Unsupported('unsupported bit width or bounds')
    q = p['locations']; d = 1 << p['bits']
    if type(q) is not list or not 1 <= len(q) <= 128 or any(type(x) is not str or not x or len(x)>40 for x in q) or len(set(q)) != len(q):
        raise Unsupported('locations')
    if p['start'] not in q or type(p['initial']) is not list or not p['initial'] or any(not integer(x,0,d-1) for x in p['initial']) or len(set(p['initial']))!=len(p['initial']):
        raise Unsupported('initial states')
    if type(p['errors']) is not list or not p['errors'] or any(x not in q for x in p['errors']) or len(set(p['errors'])) != len(p['errors']):
        raise Unsupported('error locations')
    if len(q)*d*(p['gas']+1)*(p['steps']+1) > MAX_CELLS:
        raise Unsupported('product state cap')
    if type(p['edges']) is not list or len(p['edges'])>512:
        raise Unsupported('edge cap')
    ids=[]
    for e in p['edges']:
        if type(e) is not dict or set(e)!={'id','src','dst','guard','update','gas','cost'}:
            raise Unsupported('edge fields')
        if not integer(e['id'],0,1_000_000) or e['src'] not in q or e['dst'] not in q or not integer(e['gas'],0,1) or not integer(e['cost'],0,1_000_000):
            raise Unsupported('edge types')
        a=e['guard']
        if type(a) is not list or len(a)!=2 or not all(integer(x,0,d-1) for x in a) or a[0]>a[1]:
            raise Unsupported('guard')
        u=e['update']
        if u != 'havoc':
            if type(u) is not list or len(u)!=2 or not all(integer(x,-2**31,2**31-1) for x in u):
                raise Unsupported('update')
        ids.append(e['id'])
    if len(set(ids))!=len(ids):
        raise Unsupported('duplicate edge identifier')


def successors(p: dict[str, Any], q: str, x: int) -> Iterator[tuple[dict[str, Any], int]]:
    if q in p['errors']:
        return
    d=1<<p['bits']
    for e in p['edges']:
        if e['src']==q and e['guard'][0] <= x <= e['guard'][1]:
            u=e['update']
            for y in (range(d) if u=='havoc' else [(u[0]*x+u[1])%d]):
                yield e,y


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result={}
    for k,v in pairs:
        if k in result:
            raise Unsupported('duplicate JSON key')
        result[k]=v
    return result


def load(path: str) -> dict[str, Any]:
    from pathlib import Path
    with Path(path).open('rb') as stream:
        b=stream.read(8*1024*1024+1)
    if len(b)>8*1024*1024:
        raise Unsupported('input byte cap')
    return json.loads(b,object_pairs_hook=unique_object)
