"""Exhaust every query in a declared two-location micro-language.

This is finite meta-validation, not a proof for arbitrary inputs.  The universe
is defined extensionally by a 48-edge template pool, every edge set of size at
most two, three initial-value sets, gas caps 0..2, and step caps 0..3.  For each query we compare three computation families: budget-parametric
production/checking, dense production/checking, and a forward trace oracle that
uses no dynamic programming.  These families contain two checker calls; the
study does not count producer and checker stages as four independent semantic
implementations.
Only aggregate and stratum evidence is retained; this module is the exact,
deterministic input generator.
"""
from __future__ import annotations

import argparse
import csv
from itertools import combinations
import json
from pathlib import Path
import resource
import time
from typing import Any, Iterable

from checker import check as check_dense
from frontier_checker import check as check_frontier
from frontier_oracle import enumerate_frontier
from frontier_producer import produce as produce_frontier
from producer import produce as produce_dense


INITIALS = ((0,), (1,), (0, 1))
GAS_CAPS = (0, 1, 2)
STEP_CAPS = (0, 1, 2, 3)
GUARD_UPDATES = (
    ((0, 1), (1, 0), "full-id"),
    ((0, 1), (1, 1), "full-flip"),
    ((0, 0), (1, 0), "zero-id"),
    ((0, 0), (1, 1), "zero-flip"),
    ((1, 1), (1, 0), "one-id"),
    ((1, 1), (1, 1), "one-flip"),
)
RESOURCE_PAIRS = ((0, 0), (0, 1), (1, 0), (1, 1))
DESTINATIONS = ("s", "z")


def templates() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for dst in DESTINATIONS:
        for guard, update, label in GUARD_UPDATES:
            for gas, cost in RESOURCE_PAIRS:
                result.append({
                    "dst": dst,
                    "guard": list(guard),
                    "update": list(update),
                    "gas": gas,
                    "cost": cost,
                    "label": f"{dst}-{label}-g{gas}-c{cost}",
                })
    return result


def edge_sets(pool: list[dict[str, Any]]) -> Iterable[tuple[dict[str, Any], ...]]:
    yield ()
    for item in pool:
        yield (item,)
    yield from combinations(pool, 2)


def program(case_number: int, chosen: tuple[dict[str, Any], ...], initial: tuple[int, ...],
            gas_cap: int, step_cap: int) -> dict[str, Any]:
    edges: list[dict[str, Any]] = []
    for identifier, item in enumerate(chosen):
        edges.append({
            "id": identifier,
            "src": "s",
            "dst": item["dst"],
            "guard": item["guard"],
            "update": item["update"],
            "gas": item["gas"],
            "cost": item["cost"],
        })
    return {
        "id": f"tiny-{case_number}",
        "bits": 1,
        "locations": ["s", "z"],
        "start": "s",
        "initial": list(initial),
        "errors": ["z"],
        "gas": gas_cap,
        "steps": step_cap,
        "edges": edges,
    }


def run(out: Path) -> dict[str, Any]:
    if out.exists():
        raise ValueError("output directory must not exist")
    out.mkdir(parents=True)
    pool = templates()
    strata: dict[tuple[int, int, str], dict[str, int]] = {}
    failures: list[dict[str, Any]] = []
    status_counts = {"optimal_bounded": 0, "safe_bounded": 0}
    total_frontier_points = 0
    total_candidate_pairs = 0
    max_frontier_width = 0
    max_oracle_prefixes = 0
    case_number = 0
    started = time.process_time()
    for chosen in edge_sets(pool):
        for initial in INITIALS:
            initial_name = "".join(str(x) for x in initial)
            for gas_cap in GAS_CAPS:
                for step_cap in STEP_CAPS:
                    p = program(case_number, chosen, initial, gas_cap, step_cap)
                    certificate, produced = produce_frontier(p)
                    checked = check_frontier(p, certificate)
                    dense_certificate, _ = produce_dense(p)
                    dense = check_dense(p, dense_certificate)
                    oracle = enumerate_frontier(p)
                    frontier_tuple = (checked["status"], checked["upper"], checked["initial_frontier"])
                    oracle_tuple = (oracle["status"], oracle["cost"], oracle["frontier"])
                    dense_tuple = (dense["status"], dense["upper"])
                    expected_dense = (checked["status"], checked["upper"])
                    agreement = frontier_tuple == oracle_tuple and dense_tuple == expected_dense
                    if not agreement:
                        failures.append({
                            "case": case_number,
                            "program": p,
                            "frontier": frontier_tuple,
                            "dense": dense_tuple,
                            "oracle": oracle_tuple,
                        })
                        if len(failures) >= 10:
                            raise AssertionError("ten exhaustive-universe disagreements")
                    status_counts[checked["status"]] += 1
                    total_frontier_points += produced["points"]
                    total_candidate_pairs += produced["candidate_pairs"]
                    max_frontier_width = max(max_frontier_width, produced["max_points_per_row"])
                    max_oracle_prefixes = max(max_oracle_prefixes, oracle["prefixes"])
                    key = (gas_cap, step_cap, initial_name)
                    row = strata.setdefault(key, {"cases": 0, "optimal_bounded": 0,
                                                  "safe_bounded": 0, "frontier_points": 0,
                                                  "candidate_pairs": 0, "oracle_prefixes": 0})
                    row["cases"] += 1
                    row[checked["status"]] += 1
                    row["frontier_points"] += produced["points"]
                    row["candidate_pairs"] += produced["candidate_pairs"]
                    row["oracle_prefixes"] += oracle["prefixes"]
                    case_number += 1
    with (out / "strata.csv").open("w", newline="") as stream:
        fields = ["gas", "steps", "initial", "cases", "optimal_bounded", "safe_bounded",
                  "frontier_points", "candidate_pairs", "oracle_prefixes"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for (gas_cap, step_cap, initial_name), row in sorted(strata.items()):
            writer.writerow({"gas": gas_cap, "steps": step_cap, "initial": initial_name, **row})
    specification = {
        "bits": 1,
        "locations": ["s", "z"],
        "error": "z",
        "edge_templates": len(pool),
        "edge_set_cardinalities": [0, 1, 2],
        "edge_sets": 1 + len(pool) + len(pool) * (len(pool) - 1) // 2,
        "initial_sets": [list(x) for x in INITIALS],
        "gas_caps": list(GAS_CAPS),
        "step_caps": list(STEP_CAPS),
        "guard_update_labels": [label for _, _, label in GUARD_UPDATES],
        "resource_pairs": [list(x) for x in RESOURCE_PAIRS],
        "destinations": list(DESTINATIONS),
    }
    (out / "specification.json").write_text(json.dumps(specification, indent=2, sort_keys=True) + "\n")
    summary = {
        "status": "exhaustive_micro_validation_passed" if not failures else "disagreement",
        "cases": case_number,
        "edge_templates": len(pool),
        "edge_sets": specification["edge_sets"],
        "strata": len(strata),
        "optimal_bounded": status_counts["optimal_bounded"],
        "safe_bounded": status_counts["safe_bounded"],
        "agreements": case_number - len(failures),
        "disagreements": len(failures),
        "max_frontier_width": max_frontier_width,
        "total_frontier_points": total_frontier_points,
        "total_candidate_pairs": total_candidate_pairs,
        "max_oracle_prefixes": max_oracle_prefixes,
        "cpu_seconds": time.process_time() - started,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "workers": 1,
        "finite_check_not_general_proof": True,
        "failures": failures,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        summary = run(args.out)
    except (OSError, ValueError, AssertionError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        return 1
    print(json.dumps({k: summary[k] for k in ("status", "cases", "agreements", "disagreements", "cpu_seconds")}, sort_keys=True))
    return 0 if summary["disagreements"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
