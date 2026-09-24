#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from pcrh.checker import check_certificate_object
from pcrh.core import Edge, System, dense_value_table, exhaustive_oracle, make_certificate


def main() -> int:
    rng = random.Random(9302026)
    cases = 10000
    query_checks = 0
    gaps = 0
    for index in range(cases):
        n = rng.randint(2, 5)
        states = tuple([f"q{i}:0" for i in range(n - 1)] + ["err"])
        edge_count = rng.randint(0, min(10, n * n))
        edges = []
        used = set()
        for j in range(edge_count):
            src = rng.choice(states)
            dst = rng.choice(states)
            key = (src, dst, j)
            if key in used:
                continue
            used.add(key)
            edges.append(Edge(f"e{j}", src, dst, rng.randint(0, 2), rng.randint(0, 7)))
        horizon = rng.randint(0, 4)
        gas_bound = rng.randint(0, 4)
        concrete = System(states, states[0], frozenset({"err"}), tuple(edges), horizon, gas_bound)
        alpha = {s: ("err" if s == "err" else "control") for s in states}
        cert = make_certificate(concrete, alpha, "coarse-random")
        checked = check_certificate_object(cert)
        gaps += checked.gap_budgets
        exact = dense_value_table(concrete)
        for budget in range(gas_bound + 1):
            oracle, _, _ = exhaustive_oracle(concrete, budget)
            dp = exact[horizon][states[0]][budget]
            dp_value = None if dp == float("inf") else int(dp)
            if oracle != dp_value:
                raise AssertionError((index, budget, oracle, dp_value))
            result = checked.results[budget]
            if result["status"] == "safe" and oracle is not None:
                raise AssertionError("false safety")
            if result["status"] == "optimal" and result["upper"] != oracle:
                raise AssertionError("false optimality")
            if result["status"] == "gap" and result["lower"] != "INF" and oracle is not None and int(result["lower"]) > oracle:
                raise AssertionError("invalid lower bound")
            query_checks += 1
    summary = {
        "schema": "pcrh-fuzz-summary-v1",
        "seed": 9302026,
        "systems": cases,
        "budget_queries": query_checks,
        "gap_results": gaps,
        "status": "pass",
    }
    path = HERE / "results" / "fuzz-summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
