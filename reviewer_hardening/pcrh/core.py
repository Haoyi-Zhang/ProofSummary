from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from heapq import heappop, heappush
from itertools import count
from math import inf
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

INF_TOKEN = "INF"


def _nat(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer (bool is rejected)")
    return value


@dataclass(frozen=True, order=True)
class Edge:
    edge_id: str
    src: str
    dst: str
    gas: int
    cost: int

    def __post_init__(self) -> None:
        if not isinstance(self.edge_id, str) or not self.edge_id:
            raise ValueError("edge_id must be a non-empty string")
        if not isinstance(self.src, str) or not self.src:
            raise ValueError("src must be a non-empty string")
        if not isinstance(self.dst, str) or not self.dst:
            raise ValueError("dst must be a non-empty string")
        _nat(self.gas, "gas")
        _nat(self.cost, "cost")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.edge_id, "src": self.src, "dst": self.dst,
                "gas": self.gas, "cost": self.cost}

    @staticmethod
    def from_dict(obj: Mapping[str, Any]) -> "Edge":
        return Edge(str(obj["id"]), str(obj["src"]), str(obj["dst"]),
                    _nat(obj["gas"], "gas"), _nat(obj["cost"], "cost"))


@dataclass(frozen=True)
class System:
    states: tuple[str, ...]
    initial: str
    errors: frozenset[str]
    edges: tuple[Edge, ...]
    horizon: int
    gas_bound: int

    def __post_init__(self) -> None:
        if not self.states or any(not isinstance(s, str) or not s for s in self.states):
            raise ValueError("states must be non-empty strings")
        if len(set(self.states)) != len(self.states):
            raise ValueError("states must be unique")
        state_set = set(self.states)
        if self.initial not in state_set:
            raise ValueError("initial state is not declared")
        if not self.errors <= state_set:
            raise ValueError("error state is not declared")
        if len({e.edge_id for e in self.edges}) != len(self.edges):
            raise ValueError("edge ids must be unique")
        for edge in self.edges:
            if edge.src not in state_set or edge.dst not in state_set:
                raise ValueError(f"edge {edge.edge_id} has undeclared endpoint")
        _nat(self.horizon, "horizon")
        _nat(self.gas_bound, "gas_bound")

    def outgoing(self) -> dict[str, tuple[Edge, ...]]:
        result: dict[str, list[Edge]] = {s: [] for s in self.states}
        for edge in self.edges:
            result[edge.src].append(edge)
        return {s: tuple(sorted(es)) for s, es in result.items()}

    def edge_map(self) -> dict[str, Edge]:
        return {edge.edge_id: edge for edge in self.edges}

    def to_dict(self) -> dict[str, Any]:
        return {
            "states": list(self.states),
            "initial": self.initial,
            "errors": sorted(self.errors),
            "edges": [edge.to_dict() for edge in sorted(self.edges)],
            "horizon": self.horizon,
            "gas_bound": self.gas_bound,
        }

    @staticmethod
    def from_dict(obj: Mapping[str, Any]) -> "System":
        states_raw = obj["states"]
        errors_raw = obj["errors"]
        edges_raw = obj["edges"]
        if not isinstance(states_raw, list) or not isinstance(errors_raw, list) or not isinstance(edges_raw, list):
            raise ValueError("states, errors, and edges must be arrays")
        return System(
            states=tuple(str(s) for s in states_raw),
            initial=str(obj["initial"]),
            errors=frozenset(str(s) for s in errors_raw),
            edges=tuple(Edge.from_dict(e) for e in edges_raw),
            horizon=_nat(obj["horizon"], "horizon"),
            gas_bound=_nat(obj["gas_bound"], "gas_bound"),
        )


def build_quotient(concrete: System, alpha: Mapping[str, str]) -> System:
    """Build the path-mixing quotient used as a sound lower-bound abstraction.

    Every concrete edge is represented by an abstract edge with identical weights.
    Quotienting may splice edges from different concrete states, hence it is an
    over-approximation.  Identical weights make the weighted-simulation check
    immediate; a checker nevertheless validates it edge by edge.
    """
    if set(alpha) != set(concrete.states):
        missing = sorted(set(concrete.states) - set(alpha))
        extra = sorted(set(alpha) - set(concrete.states))
        raise ValueError(f"alpha must be total and exact; missing={missing}, extra={extra}")
    if any(not isinstance(alpha[s], str) or not alpha[s] for s in concrete.states):
        raise ValueError("abstract state names must be non-empty strings")
    states = tuple(sorted({alpha[s] for s in concrete.states}))
    edges = tuple(
        Edge(f"abs::{edge.edge_id}", alpha[edge.src], alpha[edge.dst], edge.gas, edge.cost)
        for edge in sorted(concrete.edges)
    )
    return System(
        states=states,
        initial=alpha[concrete.initial],
        errors=frozenset(alpha[s] for s in concrete.errors),
        edges=edges,
        horizon=concrete.horizon,
        gas_bound=concrete.gas_bound,
    )


def dense_value_table(system: System) -> list[dict[str, list[int | float]]]:
    """Exact minimum error cost for every (remaining steps, state, gas budget)."""
    out = system.outgoing()
    table: list[dict[str, list[int | float]]] = []
    base: dict[str, list[int | float]] = {}
    for state in system.states:
        value = 0 if state in system.errors else inf
        base[state] = [value for _ in range(system.gas_bound + 1)]
    table.append(base)
    for h in range(1, system.horizon + 1):
        layer: dict[str, list[int | float]] = {}
        prev = table[h - 1]
        for state in system.states:
            values: list[int | float] = []
            for budget in range(system.gas_bound + 1):
                best = 0 if state in system.errors else inf
                for edge in out[state]:
                    if edge.gas <= budget:
                        suffix = prev[edge.dst][budget - edge.gas]
                        if suffix != inf:
                            best = min(best, edge.cost + suffix)
                values.append(best)
            layer[state] = values
        table.append(layer)
    return table


def encode_table(table: Sequence[Mapping[str, Sequence[int | float]]]) -> list[dict[str, list[int | str]]]:
    encoded: list[dict[str, list[int | str]]] = []
    for layer in table:
        encoded_layer: dict[str, list[int | str]] = {}
        for state in sorted(layer):
            encoded_layer[state] = [INF_TOKEN if value == inf else int(value) for value in layer[state]]
        encoded.append(encoded_layer)
    return encoded


def _heuristic(table: Sequence[Mapping[str, Sequence[int | float]]], alpha: Mapping[str, str],
               state: str, remaining_steps: int, remaining_gas: int) -> int | float:
    return table[remaining_steps][alpha[state]][remaining_gas]


def astar_witness(concrete: System, alpha: Mapping[str, str], abstract_table: Sequence[Mapping[str, Sequence[int | float]]],
                  budget: int) -> tuple[dict[str, Any] | None, int]:
    """Find an optimal concrete witness using only the abstract lower table.

    The routine never calls concrete dynamic programming.  It reopens product
    states, so admissibility (not consistency) is sufficient.
    """
    _nat(budget, "budget")
    if budget > concrete.gas_bound:
        raise ValueError("budget exceeds model gas bound")
    out = concrete.outgoing()
    start_h = _heuristic(abstract_table, alpha, concrete.initial, concrete.horizon, budget)
    if start_h == inf:
        return None, 0
    serial = count()
    start = (concrete.initial, 0, 0)  # state, gas used, steps used
    heap: list[tuple[int | float, int, int, tuple[str, int, int]]] = []
    heappush(heap, (start_h, 0, next(serial), start))
    best: dict[tuple[str, int, int], int] = {start: 0}
    parent: dict[tuple[str, int, int], tuple[tuple[str, int, int], str]] = {}
    expansions = 0
    while heap:
        f_score, path_cost, _, node = heappop(heap)
        if best.get(node) != path_cost:
            continue
        state, gas_used, steps_used = node
        remaining_steps = concrete.horizon - steps_used
        remaining_gas = budget - gas_used
        hval = _heuristic(abstract_table, alpha, state, remaining_steps, remaining_gas)
        if hval == inf or path_cost + hval != f_score:
            continue
        expansions += 1
        if state in concrete.errors:
            edge_ids: list[str] = []
            cursor = node
            while cursor != start:
                prev, edge_id = parent[cursor]
                edge_ids.append(edge_id)
                cursor = prev
            edge_ids.reverse()
            return {
                "budget": budget,
                "cost": path_cost,
                "gas": gas_used,
                "steps": steps_used,
                "edges": edge_ids,
            }, expansions
        if steps_used >= concrete.horizon:
            continue
        for edge in out[state]:
            new_gas = gas_used + edge.gas
            if new_gas > budget:
                continue
            nxt = (edge.dst, new_gas, steps_used + 1)
            new_cost = path_cost + edge.cost
            if new_cost >= best.get(nxt, inf):
                continue
            rem_steps = concrete.horizon - (steps_used + 1)
            rem_gas = budget - new_gas
            suffix_lb = _heuristic(abstract_table, alpha, edge.dst, rem_steps, rem_gas)
            if suffix_lb == inf:
                continue
            best[nxt] = new_cost
            parent[nxt] = (node, edge.edge_id)
            heappush(heap, (new_cost + suffix_lb, new_cost, next(serial), nxt))
    return None, expansions


def ucs_witness(concrete: System, budget: int) -> tuple[dict[str, Any] | None, int]:
    """Uniform-cost baseline with no abstract heuristic."""
    _nat(budget, "budget")
    if budget > concrete.gas_bound:
        raise ValueError("budget exceeds model gas bound")
    out = concrete.outgoing()
    serial = count()
    start = (concrete.initial, 0, 0)
    heap: list[tuple[int, int, tuple[str, int, int]]] = [(0, next(serial), start)]
    best = {start: 0}
    parent: dict[tuple[str, int, int], tuple[tuple[str, int, int], str]] = {}
    expansions = 0
    while heap:
        cost_so_far, _, node = heappop(heap)
        if best.get(node) != cost_so_far:
            continue
        state, gas_used, steps_used = node
        expansions += 1
        if state in concrete.errors:
            ids: list[str] = []
            cursor = node
            while cursor != start:
                prev, edge_id = parent[cursor]
                ids.append(edge_id)
                cursor = prev
            ids.reverse()
            return {"budget": budget, "cost": cost_so_far, "gas": gas_used,
                    "steps": steps_used, "edges": ids}, expansions
        if steps_used >= concrete.horizon:
            continue
        for edge in out[state]:
            new_gas = gas_used + edge.gas
            if new_gas > budget:
                continue
            nxt = (edge.dst, new_gas, steps_used + 1)
            new_cost = cost_so_far + edge.cost
            if new_cost < best.get(nxt, inf):
                best[nxt] = new_cost
                parent[nxt] = (node, edge.edge_id)
                heappush(heap, (new_cost, next(serial), nxt))
    return None, expansions


def exhaustive_oracle(concrete: System, budget: int) -> tuple[int | None, list[str] | None, int]:
    """Forward path enumeration used only as a tiny-model oracle.

    It deliberately does not call either dynamic programming implementation or
    either search routine.  The final count reports complete path prefixes seen.
    """
    out = concrete.outgoing()
    best_cost: int | None = None
    best_path: list[str] | None = None
    prefixes = 0

    def visit(state: str, gas: int, cost_value: int, steps: int, path: list[str]) -> None:
        nonlocal best_cost, best_path, prefixes
        prefixes += 1
        if state in concrete.errors:
            if best_cost is None or cost_value < best_cost or (cost_value == best_cost and path < (best_path or [])):
                best_cost = cost_value
                best_path = list(path)
            return
        if steps == concrete.horizon:
            return
        for edge in out[state]:
            if gas + edge.gas <= budget:
                path.append(edge.edge_id)
                visit(edge.dst, gas + edge.gas, cost_value + edge.cost, steps + 1, path)
                path.pop()

    visit(concrete.initial, 0, 0, 0, [])
    return best_cost, best_path, prefixes


def make_certificate(concrete: System, alpha: Mapping[str, str], abstraction_name: str) -> dict[str, Any]:
    abstract = build_quotient(concrete, alpha)
    table = dense_value_table(abstract)
    witnesses: dict[str, Any] = {}
    claims: dict[str, Any] = {}
    search_metrics: dict[str, Any] = {}
    for budget in range(concrete.gas_bound + 1):
        witness, expansions = astar_witness(concrete, alpha, table, budget)
        lb = table[concrete.horizon][abstract.initial][budget]
        lb_json: int | str = INF_TOKEN if lb == inf else int(lb)
        if witness is not None:
            witnesses[str(budget)] = witness
            upper: int | str = int(witness["cost"])
        else:
            upper = INF_TOKEN
        if lb == inf:
            status = "safe"
        elif witness is not None and witness["cost"] == int(lb):
            status = "optimal"
        else:
            status = "gap"
        claims[str(budget)] = {"status": status, "lower": lb_json, "upper": upper}
        search_metrics[str(budget)] = {"astar_expansions": expansions}
    concrete_object = concrete.to_dict()
    digest = hashlib.sha256(json.dumps(concrete_object, sort_keys=True,
                                      separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()
    return {
        "schema": "pcrh-sandwich-certificate-v1",
        "semantics": {
            "path_length": "at most horizon edges",
            "budget": "sum(edge.gas) <= query budget",
            "objective": "minimum non-negative path cost to any error state",
        },
        "concrete": concrete_object,
        "model_binding": {"canonical_sha256": digest},
        "abstraction": {
            "name": abstraction_name,
            "alpha": {s: alpha[s] for s in sorted(alpha)},
            "system": abstract.to_dict(),
            "simulation_obligation": "each concrete edge is covered by an abstract edge with no larger gas or cost",
        },
        "lower_table": encode_table(table),
        "witnesses": witnesses,
        "claims": claims,
        "untrusted_metrics": search_metrics,
        "producer_contract": {
            "lower": "abstract quotient dynamic program",
            "upper": "concrete A* using only the checked abstract lower table",
            "concrete_exact_dp_used_by_producer": False,
        },
    }
