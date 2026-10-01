"""Exact budget-parametric Pareto-frontier certificate producer.

For every control/data state and remaining-step layer, the producer records the
nondominated pairs (gas consumed, witness cost) of first-error paths. One
certificate answers every gas query from zero through the declared cap without
expanding a gas dimension. The independent checker does not import this file.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable, Iterable

MAX_ROWS = 200_000
MAX_WORK = 200_000
MAX_GAS = 1_000_000


class Unsupported(ValueError):
    """The requested finite instance is outside the declared fragment."""


class Exhausted(RuntimeError):
    """The bounded construction exceeded its explicit work or CPU limit."""


class WorkBudget:
    def __init__(self, limit: int = MAX_WORK, seconds: float = 180.0,
                 *, started: float | None = None) -> None:
        self.limit = limit
        self.seconds = seconds
        self.work = 0
        self.started = time.process_time() if started is None else started

    def check_time(self) -> None:
        if time.process_time() - self.started > self.seconds:
            raise Exhausted("frontier CPU limit")

    def tick(self, n: int = 1) -> None:
        self.work += n
        if self.work > self.limit:
            raise Exhausted("frontier candidate limit")
        # Check on every increment; callers also check rows/edges and before return,
        # so zero-candidate and sub-128-candidate instances cannot bypass the guard.
        self.check_time()


def _integer(value: Any, lo: int, hi: int) -> bool:
    return type(value) is int and lo <= value <= hi


def validate(p: Any) -> None:
    fields = {"id", "bits", "locations", "start", "initial", "errors", "gas", "steps", "edges"}
    if type(p) is not dict or set(p) != fields:
        raise Unsupported("unsupported input fields")
    if type(p["id"]) is not str or not 1 <= len(p["id"]) <= 80:
        raise Unsupported("case identifier")
    if (not _integer(p["bits"], 1, 6) or not _integer(p["gas"], 0, MAX_GAS) or
            not _integer(p["steps"], 0, 128)):
        raise Unsupported("unsupported bit width or bounds")
    locations = p["locations"]
    width = 1 << p["bits"]
    if (type(locations) is not list or not 1 <= len(locations) <= 128 or
            any(type(q) is not str or not q or len(q) > 40 for q in locations) or
            len(set(locations)) != len(locations)):
        raise Unsupported("locations")
    if p["start"] not in locations:
        raise Unsupported("start")
    if (type(p["initial"]) is not list or not p["initial"] or
            any(not _integer(x, 0, width - 1) for x in p["initial"]) or
            len(set(p["initial"])) != len(p["initial"])):
        raise Unsupported("initial states")
    if (type(p["errors"]) is not list or not p["errors"] or
            any(q not in locations for q in p["errors"]) or
            len(set(p["errors"])) != len(p["errors"])):
        raise Unsupported("error locations")
    if len(locations) * width * (p["steps"] + 1) > MAX_ROWS:
        raise Unsupported("frontier row cap")
    if type(p["edges"]) is not list or len(p["edges"]) > 512:
        raise Unsupported("edge cap")
    identifiers: list[int] = []
    for edge in p["edges"]:
        if type(edge) is not dict or set(edge) != {
            "id", "src", "dst", "guard", "update", "gas", "cost"
        }:
            raise Unsupported("edge fields")
        if (not _integer(edge["id"], 0, 1_000_000) or edge["src"] not in locations or
                edge["dst"] not in locations or not _integer(edge["gas"], 0, 1) or
                not _integer(edge["cost"], 0, 1_000_000)):
            raise Unsupported("edge types")
        guard = edge["guard"]
        if (type(guard) is not list or len(guard) != 2 or
                not all(_integer(value, 0, width - 1) for value in guard) or
                guard[0] > guard[1]):
            raise Unsupported("guard")
        update = edge["update"]
        if update != "havoc":
            if (type(update) is not list or len(update) != 2 or
                    not all(_integer(value, -2**31, 2**31 - 1) for value in update)):
                raise Unsupported("update")
        identifiers.append(edge["id"])
    if len(set(identifiers)) != len(identifiers):
        raise Unsupported("duplicate edge identifier")


def successors(p: dict[str, Any], q: str, x: int, *, budget: WorkBudget | None = None,
               counters: dict[str, int] | None = None) -> Iterable[tuple[dict[str, Any], int]]:
    if q in p["errors"]:
        return ()
    width = 1 << p["bits"]
    out: list[tuple[dict[str, Any], int]] = []
    for edge in p["edges"]:
        if budget is not None:
            budget.check_time()
        if counters is not None:
            counters["edge_guard_checks"] += 1
        if edge["src"] != q or not edge["guard"][0] <= x <= edge["guard"][1]:
            continue
        update = edge["update"]
        values = range(width) if update == "havoc" else ((update[0] * x + update[1]) % width,)
        for y in values:
            if budget is not None:
                budget.check_time()
            if counters is not None:
                counters["successor_visits"] += 1
            out.append((edge, y))
    return out


def pareto(pairs: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    """Canonical componentwise-minimal gas/cost pairs."""
    by_gas: dict[int, int] = {}
    for gas, cost in pairs:
        current = by_gas.get(gas)
        if current is None or cost < current:
            by_gas[gas] = cost
    result: list[tuple[int, int]] = []
    best_cost: int | None = None
    for gas in sorted(by_gas):
        cost = by_gas[gas]
        if best_cost is None or cost < best_cost:
            result.append((gas, cost))
            best_cost = cost
    return tuple(result)


def compute_frontiers(p: dict[str, Any], *, max_work: int = MAX_WORK,
                      seconds: float = 180.0, started: float | None = None
                      ) -> tuple[dict[tuple[str, int, int], tuple[tuple[int, int], ...]],
                                 dict[str, int]]:
    validate(p)
    budget = WorkBudget(max_work, seconds, started=started)
    budget.check_time()
    width = 1 << p["bits"]
    gas_cap = p["gas"]
    frontiers: dict[tuple[str, int, int], tuple[tuple[int, int], ...]] = {}
    total_points = 0
    max_points = 0
    candidate_pairs = 0
    row_visits = 0
    counters = {"edge_guard_checks": 0, "successor_visits": 0}
    temporary_candidate_peak = 0
    temporary_successor_peak = 0
    for h in range(p["steps"] + 1):
        for q in p["locations"]:
            for x in range(width):
                budget.check_time()
                row_visits += 1
                key = (q, x, h)
                if q in p["errors"]:
                    front = ((0, 0),)
                elif h == 0:
                    front = ()
                else:
                    candidates: list[tuple[int, int]] = []
                    row_successors = list(successors(p, q, x, budget=budget, counters=counters))
                    temporary_successor_peak = max(temporary_successor_peak, len(row_successors))
                    for edge, y in row_successors:
                        budget.check_time()
                        for gas, cost in frontiers[edge["dst"], y, h - 1]:
                            budget.tick()
                            candidate_pairs += 1
                            shifted_gas = edge["gas"] + gas
                            if shifted_gas <= gas_cap:
                                candidates.append((shifted_gas, edge["cost"] + cost))
                    temporary_candidate_peak = max(temporary_candidate_peak, len(candidates))
                    front = pareto(candidates)
                frontiers[key] = front
                total_points += len(front)
                max_points = max(max_points, len(front))
    budget.check_time()
    return frontiers, {
        "rows": len(frontiers),
        "row_visits": row_visits,
        "points": total_points,
        "max_points_per_row": max_points,
        "candidate_pairs": candidate_pairs,
        "edge_guard_checks": counters["edge_guard_checks"],
        "successor_visits": counters["successor_visits"],
        "temporary_candidate_peak": temporary_candidate_peak,
        "temporary_successor_peak": temporary_successor_peak,
        "input_edge_records": len(p["edges"]),
        "work": budget.work,
    }


def _choose_initial(p: dict[str, Any],
                    frontiers: dict[tuple[str, int, int], tuple[tuple[int, int], ...]]
                    ) -> tuple[int, tuple[int, int]] | None:
    choices: list[tuple[int, int, int]] = []
    for initial in p["initial"]:
        for gas, cost in frontiers[p["start"], initial, p["steps"]]:
            choices.append((cost, gas, initial))
    if not choices:
        return None
    cost, gas, initial = min(choices)
    return initial, (gas, cost)


def extract_witness(p: dict[str, Any],
                    frontiers: dict[tuple[str, int, int], tuple[tuple[int, int], ...]],
                    *, check_time: Callable[[], None] | None = None) -> dict[str, Any] | None:
    if check_time is not None:
        check_time()
    chosen = _choose_initial(p, frontiers)
    if chosen is None:
        return None
    initial, target = chosen
    q = p["start"]
    x = initial
    h = p["steps"]
    gas, cost = target
    edge_ids: list[int] = []
    values: list[int] = [initial]
    while q not in p["errors"]:
        if check_time is not None:
            check_time()
        if h == 0:
            raise AssertionError("frontier pair has no derivation")
        found: tuple[dict[str, Any], int] | None = None
        options = sorted(successors(p, q, x), key=lambda item: (item[0]["id"], item[1]))
        for edge, y in options:
            if check_time is not None:
                check_time()
            remaining = (gas - edge["gas"], cost - edge["cost"])
            if remaining[0] < 0 or remaining[1] < 0:
                continue
            if remaining in frontiers[edge["dst"], y, h - 1]:
                found = (edge, y)
                break
        if found is None:
            raise AssertionError("frontier normalization lost all derivations")
        edge, y = found
        edge_ids.append(edge["id"])
        values.append(y)
        gas -= edge["gas"]
        cost -= edge["cost"]
        q, x, h = edge["dst"], y, h - 1
    if check_time is not None:
        check_time()
    if (gas, cost) != (0, 0):
        raise AssertionError("witness derivation ended with residual resources")
    return {
        "initial": initial,
        "edges": edge_ids,
        "values": values,
        "steps": len(edge_ids),
        "gas": target[0],
        "cost": target[1],
    }


def produce(p: dict[str, Any], *, max_work: int = MAX_WORK,
            seconds: float = 180.0) -> tuple[dict[str, Any], dict[str, int]]:
    started = time.process_time()

    def check_time() -> None:
        if time.process_time() - started > seconds:
            raise Exhausted("frontier CPU limit")

    check_time()
    frontiers, statistics = compute_frontiers(
        p, max_work=max_work, seconds=seconds, started=started
    )
    rows: list[list[Any]] = []
    for qi, q in enumerate(p["locations"]):
        for x in range(1 << p["bits"]):
            for h in range(p["steps"] + 1):
                check_time()
                rows.append([qi, x, h, [[gas, cost] for gas, cost in frontiers[q, x, h]]])
    witness = extract_witness(p, frontiers, check_time=check_time)
    check_time()
    certificate = {"query": p, "witness": witness, "frontiers": rows}
    return certificate, statistics


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise Unsupported("duplicate JSON key")
        out[key] = value
    return out


def load(path: str) -> Any:
    with Path(path).open("rb") as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise Unsupported("input byte cap")
    return json.loads(raw, object_pairs_hook=unique_object)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()
    try:
        certificate, statistics = produce(load(args.input))
        Path(args.output).write_text(json.dumps(certificate, separators=(",", ":")) + "\n")
        print(json.dumps({"result": "certificate_generated", "statistics": statistics}, sort_keys=True))
        return 0
    except (Unsupported, Exhausted, OSError, ValueError, KeyError, TypeError,
            RecursionError) as exc:
        print(json.dumps({"result": "unknown", "reason": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
