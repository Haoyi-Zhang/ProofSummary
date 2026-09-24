"""Deterministic cases for budget-parametric frontier certificates.

The cases separate three phenomena: resource/cost tradeoffs that force a wide
Pareto frontier, exponentially many traces that collapse to one point, and a
large gas cap that would make explicit gas-product construction infeasible.
They are mathematical transition systems, not C programs.
"""
from __future__ import annotations

from typing import Any


def edge(i: int, src: str, dst: str, *, gas: int = 0, cost: int = 0,
         guard: list[int] | None = None, update: list[int] | str | None = None) -> dict[str, Any]:
    return {
        "id": i,
        "src": src,
        "dst": dst,
        "guard": [0, 1] if guard is None else guard,
        "update": [1, 0] if update is None else update,
        "gas": gas,
        "cost": cost,
    }


def program(name: str, locations: list[str], edges: list[dict[str, Any]], *,
            gas: int, steps: int, bits: int = 1,
            initial: list[int] | None = None) -> dict[str, Any]:
    return {
        "id": name,
        "bits": bits,
        "locations": locations,
        "start": locations[0],
        "initial": [0] if initial is None else initial,
        "errors": [locations[-1]],
        "gas": gas,
        "steps": steps,
        "edges": edges,
    }


def tradeoff_chain(length: int) -> dict[str, Any]:
    """Exactly ``length + 1`` nondominated (gas,cost) pairs at the start."""
    locations = [f"q{i}" for i in range(length + 1)]
    edges: list[dict[str, Any]] = []
    identifier = 0
    for i in range(length):
        edges.append(edge(identifier, locations[i], locations[i + 1], gas=0, cost=1))
        identifier += 1
        edges.append(edge(identifier, locations[i], locations[i + 1], gas=1, cost=0))
        identifier += 1
    return program(f"tradeoff-{length}", locations, edges, gas=length, steps=length)


def dominated_diamond(length: int) -> dict[str, Any]:
    """Two choices per layer, but the zero-resource choice dominates throughout."""
    locations = [f"q{i}" for i in range(length + 1)]
    edges: list[dict[str, Any]] = []
    identifier = 0
    for i in range(length):
        edges.append(edge(identifier, locations[i], locations[i + 1], gas=0, cost=0))
        identifier += 1
        edges.append(edge(identifier, locations[i], locations[i + 1], gas=1, cost=1))
        identifier += 1
    return program(f"dominated-{length}", locations, edges, gas=length, steps=length)


def single_path(length: int, gas_cap: int = 1_000_000) -> dict[str, Any]:
    """One long path under a gas cap unrelated to the number of reachable consumptions."""
    locations = [f"q{i}" for i in range(length + 1)]
    edges = [edge(i, locations[i], locations[i + 1], gas=1, cost=(i % 5) + 1)
             for i in range(length)]
    return program(f"single-{length}-g{gas_cap}", locations, edges, gas=gas_cap, steps=length)


def mixed_havoc() -> dict[str, Any]:
    """Guards, modular affine updates, havoc, and multiple initial valuations."""
    return {
        "id": "mixed-havoc-frontier",
        "bits": 3,
        "locations": ["s", "a", "b", "z"],
        "start": "s",
        "initial": [0, 3],
        "errors": ["z"],
        "gas": 3,
        "steps": 4,
        "edges": [
            edge(0, "s", "a", gas=1, cost=1, guard=[0, 7], update="havoc"),
            edge(1, "s", "b", gas=0, cost=6, guard=[0, 7], update=[1, 1]),
            edge(2, "a", "a", gas=0, cost=1, guard=[0, 6], update=[1, 1]),
            edge(3, "a", "z", gas=1, cost=0, guard=[7, 7], update=[1, 0]),
            edge(4, "a", "b", gas=0, cost=2, guard=[0, 7], update=[2, 1]),
            edge(5, "b", "z", gas=0, cost=2, guard=[0, 7], update=[1, 0]),
        ],
    }


def safe_large_gas() -> dict[str, Any]:
    return program("safe-large-gas", ["s", "z"],
                   [edge(0, "s", "s", gas=1, cost=0)],
                   gas=1_000_000, steps=128)


def stress_cases() -> list[tuple[dict[str, Any], str]]:
    cases: list[tuple[dict[str, Any], str]] = []
    for length in (8, 16, 24, 32):
        cases.append((tradeoff_chain(length), "linear-width-worst-case"))
    for length in (8, 16, 24, 32):
        cases.append((dominated_diamond(length), "exponential-traces-collapsed"))
    for length in (32, 64, 96, 127):
        cases.append((single_path(length), "large-gas-single-frontier"))
    cases.append((mixed_havoc(), "mixed-semantics"))
    cases.append((safe_large_gas(), "large-gas-safe"))
    return cases
