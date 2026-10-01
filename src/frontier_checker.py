"""Independent checker for exact budget-parametric Pareto certificates.

Trust boundary: Python, JSON parsing, the external finite CFG, and this file.
The checker imports no producer, search, model, Pareto, or oracle code. It
replays the explicit witness and independently reconstructs every local
frontier recurrence. This is finite executable checking, not a mechanized
proof of the Python implementation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any, Iterable

MAX_ROWS = 200_000
MAX_WORK = 200_000
MAX_GAS = 1_000_000
MAX_JSON_BYTES = 8 * 1024 * 1024


class Reject(ValueError):
    pass


class Limit(RuntimeError):
    pass


def nat(value: Any, high: int = 10**12) -> bool:
    return type(value) is int and 0 <= value <= high


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise Reject(reason)


def _same_json(left: Any, right: Any) -> bool:
    """Type-sensitive structural equality for independently decoded JSON."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(_same_json(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same_json(a, b) for a, b in zip(left, right))
    return left == right


def decode_bytes(raw: bytes, *, max_bytes: int = MAX_JSON_BYTES) -> Any:
    require(type(raw) is bytes, "JSON input must be bytes")
    if len(raw) > max_bytes:
        raise Limit("file byte cap")

    def object_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out

    def reject_constant(token: str) -> Any:
        raise Reject("non-finite JSON number: " + token)

    return json.loads(raw, object_pairs_hook=object_pairs, parse_constant=reject_constant)


def decode(path: str | Path, *, max_bytes: int = MAX_JSON_BYTES) -> Any:
    with Path(path).open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    return decode_bytes(raw, max_bytes=max_bytes)


def check_bytes(query_bytes: bytes, certificate_bytes: bytes, *,
                max_bytes: int = MAX_JSON_BYTES, max_work: int = MAX_WORK,
                seconds: float = 180.0) -> dict[str, Any]:
    """Decode separately supplied bounded byte strings and check them."""
    query = decode_bytes(query_bytes, max_bytes=max_bytes)
    certificate = decode_bytes(certificate_bytes, max_bytes=max_bytes)
    return check(query, certificate, max_work=max_work, seconds=seconds)


def check_files(query_path: str | Path, certificate_path: str | Path, *,
                max_bytes: int = MAX_JSON_BYTES, max_work: int = MAX_WORK,
                seconds: float = 180.0) -> dict[str, Any]:
    with Path(query_path).open("rb") as stream:
        query_bytes = stream.read(max_bytes + 1)
    with Path(certificate_path).open("rb") as stream:
        certificate_bytes = stream.read(max_bytes + 1)
    return check_bytes(query_bytes, certificate_bytes, max_bytes=max_bytes,
                       max_work=max_work, seconds=seconds)


def canonical(candidates: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    by_gas: dict[int, int] = {}
    for gas, cost in candidates:
        old = by_gas.get(gas)
        if old is None or cost < old:
            by_gas[gas] = cost
    result: list[tuple[int, int]] = []
    best: int | None = None
    for gas in sorted(by_gas):
        cost = by_gas[gas]
        if best is None or cost < best:
            result.append((gas, cost))
            best = cost
    return tuple(result)


def check(p: Any, certificate: Any, *, max_work: int = MAX_WORK,
          seconds: float = 180.0) -> dict[str, Any]:
    started = time.process_time()

    def check_deadline() -> None:
        if time.process_time() - started > seconds:
            raise Limit("frontier CPU cap")

    check_deadline()
    fields = {"id", "bits", "locations", "start", "initial", "errors", "gas", "steps", "edges"}
    require(type(p) is dict and set(p) == fields, "input fields")
    require(type(p["id"]) is str and 0 < len(p["id"]) <= 80, "input identifier")
    require(nat(p["bits"], 6) and p["bits"] >= 1, "bit width")
    require(nat(p["gas"], MAX_GAS) and nat(p["steps"], 128), "query bounds")
    locations = p["locations"]
    width = 1 << p["bits"]
    gas_cap = p["gas"]
    step_cap = p["steps"]
    require(type(locations) is list and 0 < len(locations) <= 128, "locations")
    require(all(type(q) is str and 0 < len(q) <= 40 for q in locations), "location names")
    require(len(set(locations)) == len(locations), "duplicate locations")
    require(type(p["start"]) is str and p["start"] in locations, "start location")
    require(type(p["initial"]) is list and p["initial"], "initial valuations")
    require(all(nat(x, width - 1) for x in p["initial"]), "initial valuations")
    require(len(set(p["initial"])) == len(p["initial"]), "duplicate initial valuations")
    require(type(p["errors"]) is list and p["errors"], "error locations")
    require(all(type(q) is str and q in locations for q in p["errors"]), "error locations")
    require(len(set(p["errors"])) == len(p["errors"]), "duplicate error locations")
    row_count = len(locations) * width * (step_cap + 1)
    if row_count > MAX_ROWS:
        raise Limit("frontier row cap")
    require(type(p["edges"]) is list and len(p["edges"]) <= 512, "edges")
    edges: dict[int, dict[str, Any]] = {}
    outgoing: dict[str, list[dict[str, Any]]] = {q: [] for q in locations}
    for edge in p["edges"]:
        check_deadline()
        require(type(edge) is dict and set(edge) == {
            "id", "src", "dst", "guard", "update", "gas", "cost"
        }, "edge fields")
        require(nat(edge["id"], 1_000_000) and edge["id"] not in edges, "edge identifier")
        require(type(edge["src"]) is str and edge["src"] in outgoing, "edge source")
        require(type(edge["dst"]) is str and edge["dst"] in outgoing, "edge destination")
        require(nat(edge["gas"], 1) and nat(edge["cost"], 1_000_000), "edge resources")
        guard = edge["guard"]
        require(type(guard) is list and len(guard) == 2, "interval guard")
        require(all(nat(value, width - 1) for value in guard) and guard[0] <= guard[1],
                "interval guard")
        update = edge["update"]
        if update != "havoc":
            require(type(update) is list and len(update) == 2, "affine update")
            require(all(type(value) is int and -2**31 <= value < 2**31 for value in update),
                    "affine update")
        edges[edge["id"]] = edge
        outgoing[edge["src"]].append(edge)
    check_deadline()

    require(type(certificate) is dict and set(certificate) == {"query", "witness", "frontiers"},
            "certificate fields")
    require(_same_json(certificate["query"], p), "certificate/query mismatch")

    witness = certificate["witness"]
    upper: int | None = None
    witnessed_gas: int | None = None
    witnessed_initial: int | None = None
    if witness is not None:
        require(type(witness) is dict and set(witness) == {
            "initial", "edges", "values", "steps", "gas", "cost"
        }, "witness fields")
        require(nat(witness["initial"], width - 1) and witness["initial"] in p["initial"],
                "witness initial")
        require(type(witness["edges"]) is list and len(witness["edges"]) <= step_cap,
                "witness edges")
        require(type(witness["values"]) is list and
                len(witness["values"]) == len(witness["edges"]) + 1,
                "witness values")
        require(all(nat(x, width - 1) for x in witness["values"]), "witness values")
        require(witness["values"][0] == witness["initial"], "witness initial mismatch")
        require(nat(witness["steps"], step_cap) and witness["steps"] == len(witness["edges"]),
                "witness steps")
        require(nat(witness["gas"], gas_cap) and nat(witness["cost"]), "witness resources")
        q = p["start"]
        x = witness["initial"]
        spent = 0
        paid = 0
        for index, edge_id in enumerate(witness["edges"]):
            check_deadline()
            require(nat(edge_id, 1_000_000) and edge_id in edges, "unknown witness edge")
            edge = edges[edge_id]
            y = witness["values"][index + 1]
            require(q not in p["errors"], "witness continues after first error")
            require(edge["src"] == q and edge["guard"][0] <= x <= edge["guard"][1],
                    "disabled witness edge")
            update = edge["update"]
            require(update == "havoc" or y == (update[0] * x + update[1]) % width,
                    "witness update")
            spent += edge["gas"]
            paid += edge["cost"]
            require(spent <= gas_cap, "witness gas exhaustion")
            q, x = edge["dst"], y
        require(q in p["errors"], "witness does not reach error")
        require(spent == witness["gas"] and paid == witness["cost"],
                "witness resource mismatch")
        upper = paid
        witnessed_gas = spent
        witnessed_initial = witness["initial"]
    check_deadline()

    rows = certificate["frontiers"]
    require(type(rows) is list and len(rows) == row_count, "missing or extra frontier rows")
    profiles: dict[tuple[str, int, int], tuple[tuple[int, int], ...]] = {}
    seen: set[tuple[int, int, int]] = set()
    total_points = 0
    max_points = 0
    decoded_rows = 0
    for row in rows:
        check_deadline()
        require(type(row) is list and len(row) == 4, "frontier row format")
        qi, x, h, pairs = row
        require(nat(qi, len(locations) - 1) and nat(x, width - 1) and nat(h, step_cap),
                "frontier row index")
        index = (qi, x, h)
        require(index not in seen, "duplicate frontier row")
        seen.add(index)
        require(type(pairs) is list and len(pairs) <= min(gas_cap, h) + 1,
                "frontier size")
        decoded: list[tuple[int, int]] = []
        previous_gas = -1
        previous_cost: int | None = None
        for pair in pairs:
            check_deadline()
            require(type(pair) is list and len(pair) == 2, "frontier pair")
            gas, cost = pair
            require(nat(gas, gas_cap) and nat(cost), "frontier resource")
            require(gas > previous_gas, "non-increasing frontier gas")
            if previous_cost is not None:
                require(cost < previous_cost, "non-decreasing frontier cost")
            decoded.append((gas, cost))
            previous_gas, previous_cost = gas, cost
        profile = tuple(decoded)
        profiles[locations[qi], x, h] = profile
        decoded_rows += 1
        total_points += len(profile)
        max_points = max(max_points, len(profile))
    require(len(profiles) == row_count, "incomplete frontier domain")
    check_deadline()

    candidate_pairs = 0
    recurrence_rows = 0
    edge_guard_checks = 0
    successor_visits = 0
    temporary_candidate_peak = 0
    for h in range(step_cap + 1):
        for q in locations:
            for x in range(width):
                check_deadline()
                actual = profiles[q, x, h]
                if q in p["errors"]:
                    expected = ((0, 0),)
                elif h == 0:
                    expected = ()
                else:
                    candidates: list[tuple[int, int]] = []
                    for edge in outgoing[q]:
                        edge_guard_checks += 1
                        check_deadline()
                        if not edge["guard"][0] <= x <= edge["guard"][1]:
                            continue
                        update = edge["update"]
                        values = (range(width) if update == "havoc" else
                                  ((update[0] * x + update[1]) % width,))
                        for y in values:
                            successor_visits += 1
                            check_deadline()
                            for gas, cost in profiles[edge["dst"], y, h - 1]:
                                candidate_pairs += 1
                                if candidate_pairs > max_work:
                                    raise Limit("frontier candidate cap")
                                check_deadline()
                                shifted = edge["gas"] + gas
                                if shifted <= gas_cap:
                                    candidates.append((shifted, edge["cost"] + cost))
                    temporary_candidate_peak = max(temporary_candidate_peak, len(candidates))
                    expected = canonical(candidates)
                recurrence_rows += 1
                require(actual == expected, "invalid exact frontier recurrence")
    check_deadline()

    initial_pairs: list[tuple[int, int, int]] = []
    for initial in p["initial"]:
        check_deadline()
        for gas, cost in profiles[p["start"], initial, step_cap]:
            initial_pairs.append((cost, gas, initial))
    optimum_initial: int | None
    if not initial_pairs:
        require(witness is None, "finite witness contradicts empty exact frontier")
        status = "safe_bounded"
        optimum_cost = None
        optimum_gas = None
        optimum_initial = None
    else:
        optimum_cost, optimum_gas, optimum_initial = min(initial_pairs)
        require(witness is not None, "reachable exact frontier lacks replayable witness")
        require(upper == optimum_cost and witnessed_gas == optimum_gas and
                witnessed_initial == optimum_initial,
                "witness does not realize the canonical least outcome")
        status = "optimal_bounded"

    aggregate = canonical((gas, cost) for cost, gas, _ in initial_pairs)
    check_deadline()
    return {
        "status": status,
        "upper": optimum_cost,
        "witness_gas": optimum_gas,
        "witness_initial": optimum_initial,
        "gas_cap": gas_cap,
        "steps": step_cap,
        "rows": row_count,
        "decoded_rows": decoded_rows,
        "points": total_points,
        "max_points_per_row": max_points,
        "candidate_pairs": candidate_pairs,
        "edge_guard_checks": edge_guard_checks,
        "successor_visits": successor_visits,
        "temporary_candidate_peak": temporary_candidate_peak,
        "input_edge_records": len(p["edges"]),
        "recurrence_rows": recurrence_rows,
        "initial_frontier": [[gas, cost] for gas, cost in aggregate],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("certificate")
    args = parser.parse_args()
    try:
        result = check_files(args.input, args.certificate)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Limit as exc:
        print(json.dumps({"status": "unknown", "reason": str(exc)}, sort_keys=True))
        return 2
    except (Reject, ValueError, OSError, TypeError, KeyError, IndexError,
            RecursionError, UnicodeDecodeError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
