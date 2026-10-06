"""Deterministic rejection tests for malformed frontier certificates."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Callable

from frontier_cases import safe_large_gas, tradeoff_chain
from frontier_checker import Limit, Reject, check
from frontier_producer import produce

Mutation = tuple[str, Callable[[dict[str, Any], dict[str, Any]], None], str]


def _start_row(cert: dict[str, Any], h: int) -> list[Any]:
    for row in cert["frontiers"]:
        if row[0] == 0 and row[1] == 0 and row[2] == h:
            return row
    raise AssertionError("start row absent")


def mutations() -> list[Mutation]:
    def certificate_query_mismatch(p, c): c["query"]["gas"] -= 1
    def extra_certificate_field(p, c): c["unexpected"] = 0
    def remove_row(p, c): c["frontiers"].pop()
    def append_row(p, c): c["frontiers"].append(copy.deepcopy(c["frontiers"][-1]))
    def duplicate_index(p, c): c["frontiers"][0] = copy.deepcopy(c["frontiers"][1])
    def malformed_row(p, c): c["frontiers"][0] = [0, 0, 0]
    def out_of_range_location(p, c): c["frontiers"][0][0] = len(p["locations"])
    def noncanonical_order(p, c): _start_row(c, p["steps"])[3].reverse()
    def remove_nondominated_pair(p, c): _start_row(c, p["steps"])[3].pop()
    def alter_frontier_cost(p, c): _start_row(c, p["steps"])[3][0][1] += 1
    def duplicate_frontier_gas(p, c):
        row = _start_row(c, p["steps"])
        row[3][1][0] = row[3][0][0]
    def negative_frontier_cost(p, c): _start_row(c, p["steps"])[3][0][1] = -1
    def omit_witness(p, c): c["witness"] = None
    def alter_witness_cost(p, c): c["witness"]["cost"] += 1
    def alter_witness_gas(p, c): c["witness"]["gas"] -= 1
    def unknown_witness_edge(p, c): c["witness"]["edges"][0] = 999999
    def truncate_witness_values(p, c): c["witness"]["values"].pop()
    def wrong_witness_steps(p, c): c["witness"]["steps"] -= 1
    def wrong_witness_initial(p, c): c["witness"]["initial"] = 1
    def change_input_edge(p, c): p["edges"][0]["cost"] += 1
    return [
        ("certificate-query-mismatch", certificate_query_mismatch, "query binding"),
        ("extra-certificate-field", extra_certificate_field, "schema"),
        ("missing-frontier-row", remove_row, "totality"),
        ("extra-frontier-row", append_row, "totality"),
        ("duplicate-frontier-index", duplicate_index, "unique domain"),
        ("malformed-frontier-row", malformed_row, "row grammar"),
        ("out-of-range-location", out_of_range_location, "index bounds"),
        ("noncanonical-pair-order", noncanonical_order, "canonical order"),
        ("missing-nondominated-pair", remove_nondominated_pair, "exact recurrence"),
        ("altered-frontier-cost", alter_frontier_cost, "exact recurrence"),
        ("duplicate-frontier-gas", duplicate_frontier_gas, "canonical order"),
        ("negative-frontier-cost", negative_frontier_cost, "resource domain"),
        ("missing-reachable-witness", omit_witness, "witness existence"),
        ("altered-witness-cost", alter_witness_cost, "witness accounting"),
        ("altered-witness-gas", alter_witness_gas, "witness accounting"),
        ("unknown-witness-edge", unknown_witness_edge, "witness replay"),
        ("truncated-witness-values", truncate_witness_values, "witness grammar"),
        ("wrong-witness-step-count", wrong_witness_steps, "witness accounting"),
        ("wrong-witness-initial", wrong_witness_initial, "witness initial"),
        ("changed-input-edge", change_input_edge, "query binding"),
    ]


def run(out: Path) -> dict[str, Any]:
    if out.exists():
        raise ValueError("output directory must not exist")
    out.mkdir(parents=True)
    base_program = tradeoff_chain(6)
    base_certificate, _ = produce(base_program)
    accepted = check(base_program, base_certificate)
    results = []
    for name, mutate, obligation in mutations():
        p = copy.deepcopy(base_program)
        c = copy.deepcopy(base_certificate)
        mutate(p, c)
        try:
            check(p, c)
            status, reason = "accepted", ""
        except Limit as exc:
            status, reason = "unknown", str(exc)
        except (Reject, ValueError, KeyError, TypeError, IndexError) as exc:
            status, reason = "rejected", str(exc)
        results.append({"mutation": name, "obligation": obligation,
                        "status": status, "reason": reason})
    safe = safe_large_gas()
    safe_certificate, _ = produce(safe)
    forged = copy.deepcopy(safe_certificate)
    forged["witness"] = {"initial": 0, "edges": [], "values": [0],
                         "steps": 0, "gas": 0, "cost": 0}
    try:
        check(safe, forged)
        status, reason = "accepted", ""
    except Limit as exc:
        status, reason = "unknown", str(exc)
    except (Reject, ValueError, KeyError, TypeError, IndexError) as exc:
        status, reason = "rejected", str(exc)
    results.append({"mutation": "forged-safe-witness", "obligation": "witness replay",
                    "status": status, "reason": reason})
    summary = {
        "valid_certificate_status": accepted["status"],
        "mutations": len(results),
        "rejected": sum(r["status"] == "rejected" for r in results),
        "accepted": sum(r["status"] == "accepted" for r in results),
        "results": results,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = run(args.out)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        return 1
    print(json.dumps({key: summary[key] for key in ("mutations", "rejected", "accepted")}, sort_keys=True))
    return 0 if summary["rejected"] == summary["mutations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
