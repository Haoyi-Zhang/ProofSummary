"""Independent exhaustive first-error oracle for complete initial Pareto fronts.

This oracle performs forward trace enumeration without dynamic programming,
state dominance, producer helpers, or checker recurrence code.  It is intended
only for small discriminating controls.
"""
from __future__ import annotations

import time
from typing import Any


def _pareto(pairs: list[tuple[int, int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for gas, cost in sorted(set(pairs)):
        if any(old_gas <= gas and old_cost <= cost for old_gas, old_cost in map(tuple, result)):
            continue
        result.append([gas, cost])
    return result


def enumerate_frontier(p: dict[str, Any], *, max_prefixes: int = 200_000,
                       seconds: float = 180.0) -> dict[str, Any]:
    started = time.process_time()
    width = 1 << p["bits"]
    stack = [(p["start"], x, 0, 0, 0) for x in p["initial"]]
    pairs: list[tuple[int, int]] = []
    prefixes = 0
    first_errors = 0
    while stack:
        q, x, gas, steps, cost = stack.pop()
        prefixes += 1
        if prefixes > max_prefixes or (prefixes % 128 == 0 and time.process_time() - started > seconds):
            return {"status": "unknown", "prefixes": prefixes - 1, "error_traces": first_errors, "frontier": None}
        if q in p["errors"]:
            pairs.append((gas, cost))
            first_errors += 1
            continue
        if steps == p["steps"]:
            continue
        for edge in p["edges"]:
            if edge["src"] != q or not edge["guard"][0] <= x <= edge["guard"][1]:
                continue
            new_gas = gas + edge["gas"]
            if new_gas > p["gas"]:
                continue
            for y in range(width):
                update = edge["update"]
                if update != "havoc" and (update[0] * x + update[1] - y) % width != 0:
                    continue
                stack.append((edge["dst"], y, new_gas, steps + 1, cost + edge["cost"]))
    frontier = _pareto(pairs)
    return {
        "status": "safe_bounded" if not frontier else "optimal_bounded",
        "cost": None if not frontier else min(cost for _, cost in frontier),
        "frontier": frontier,
        "prefixes": prefixes,
        "error_traces": first_errors,
    }
