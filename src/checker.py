"""Independent checker for finite resource-indexed lower-bound certificates.

Trust boundary: Python, JSON parsing, the externally supplied mathematical CFG,
and this file. No imports from the producer, model, search or oracle. This is
executable finite checking, not a machine-checked proof of this implementation.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time
from typing import Any

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
    """Type-sensitive structural equality for decoded JSON values."""
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

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
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
                max_bytes: int = MAX_JSON_BYTES, max_work: int = 200_000,
                seconds: float = 180.0) -> dict[str, Any]:
    """Decode independent bounded byte strings and check the certificate."""
    query = decode_bytes(query_bytes, max_bytes=max_bytes)
    certificate = decode_bytes(certificate_bytes, max_bytes=max_bytes)
    return check(query, certificate, max_work=max_work, seconds=seconds)


def check_files(query_path: str | Path, certificate_path: str | Path, *,
                max_bytes: int = MAX_JSON_BYTES, max_work: int = 200_000,
                seconds: float = 180.0) -> dict[str, Any]:
    with Path(query_path).open("rb") as stream:
        query_bytes = stream.read(max_bytes + 1)
    with Path(certificate_path).open("rb") as stream:
        certificate_bytes = stream.read(max_bytes + 1)
    return check_bytes(query_bytes, certificate_bytes, max_bytes=max_bytes,
                       max_work=max_work, seconds=seconds)


def check(p: Any, cert: Any, *, max_work: int = 200_000,
          seconds: float = 180.0) -> dict[str, Any]:
    started = time.process_time()

    def check_deadline() -> None:
        if time.process_time() - started > seconds:
            raise Limit("CPU cap")

    check_deadline()
    require(type(p) is dict and set(p) == {
        "id", "bits", "locations", "start", "initial", "errors", "gas", "steps", "edges"
    }, "input fields")
    require(type(p["id"]) is str and 0 < len(p["id"]) <= 80, "input identifier")
    require(nat(p["bits"], 6) and p["bits"] >= 1, "bit width")
    require(nat(p["gas"], 128) and nat(p["steps"], 128), "query bounds")
    locations = p["locations"]
    width = 1 << p["bits"]
    gas_cap = p["gas"]
    step_cap = p["steps"]
    require(type(locations) is list and 0 < len(locations) <= 128 and
            all(type(q) is str and 0 < len(q) <= 40 for q in locations), "locations")
    require(len(set(locations)) == len(locations), "duplicate locations")
    require(type(p["start"]) is str and p["start"] in locations, "start location")
    for name in ("initial", "errors"):
        require(type(p[name]) is list and len(p[name]) > 0, name)
    require(all(nat(x, width - 1) for x in p["initial"]) and
            len(set(p["initial"])) == len(p["initial"]), "initial valuations")
    require(all(type(q) is str and q in locations for q in p["errors"]) and
            len(set(p["errors"])) == len(p["errors"]), "error locations")
    cells = len(locations) * width * (gas_cap + 1) * (step_cap + 1)
    if cells > 200_000:
        raise Limit("product state cap")
    require(type(p["edges"]) is list and len(p["edges"]) <= 512, "edges")
    edges: dict[int, dict[str, Any]] = {}
    outgoing: dict[str, list[dict[str, Any]]] = {q: [] for q in locations}
    for edge in p["edges"]:
        check_deadline()
        require(type(edge) is dict and set(edge) == {
            "id", "src", "dst", "guard", "update", "gas", "cost"
        }, "edge fields")
        require(nat(edge["id"], 1_000_000) and edge["id"] not in edges, "edge identifier")
        require(type(edge["src"]) is str and type(edge["dst"]) is str and
                edge["src"] in outgoing and edge["dst"] in outgoing, "edge endpoints")
        require(nat(edge["cost"], 1_000_000) and nat(edge["gas"], 1), "edge resources")
        guard = edge["guard"]
        update = edge["update"]
        require(type(guard) is list and len(guard) == 2 and
                all(nat(value, width - 1) for value in guard) and guard[0] <= guard[1],
                "interval guard")
        if update != "havoc":
            require(type(update) is list and len(update) == 2 and
                    all(type(value) is int and -2**31 <= value < 2**31 for value in update),
                    "affine update")
        edges[edge["id"]] = edge
        outgoing[edge["src"]].append(edge)
    check_deadline()

    require(type(cert) is dict and set(cert) == {"query", "witness", "bounds"},
            "certificate fields")
    # The query is independently supplied to the consumer.  Type-sensitive
    # structural comparison prevents True/1 and 1.0/1 from binding as equal.
    require(_same_json(cert["query"], p), "certificate/query mismatch")
    witness = cert["witness"]
    upper: int | None = None
    if witness is not None:
        require(type(witness) is dict and set(witness) == {"initial", "edges", "values", "cost"},
                "witness fields")
        require(nat(witness["initial"], width - 1) and witness["initial"] in p["initial"],
                "witness initial value")
        require(type(witness["edges"]) is list and len(witness["edges"]) <= step_cap,
                "witness length")
        require(type(witness["values"]) is list and
                len(witness["values"]) == len(witness["edges"]) + 1 and
                all(nat(x, width - 1) for x in witness["values"]), "witness valuations")
        require(witness["values"][0] == witness["initial"], "witness initial valuation mismatch")
        require(nat(witness["cost"]), "witness cost type")
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
            q = edge["dst"]
            x = y
        require(q in p["errors"], "witness does not reach error")
        require(paid == witness["cost"], "witness cost mismatch")
        upper = paid
    check_deadline()

    rows = cert["bounds"]
    require(type(rows) is list and len(rows) == len(locations) * width * (step_cap + 1),
            "missing or extra bound rows")
    bounds: dict[tuple[str, int, int, int], int | float] = {}
    seen: set[tuple[int, int, int]] = set()
    segment_count = 0
    for row in rows:
        check_deadline()
        require(type(row) is list and len(row) == 4, "bound row format")
        qi, x, h, segments = row
        require(nat(qi, len(locations) - 1) and nat(x, width - 1) and nat(h, step_cap),
                "bound row index")
        index = (qi, x, h)
        require(index not in seen, "duplicate bound row")
        seen.add(index)
        require(type(segments) is list and 1 <= len(segments) <= gas_cap + 1, "segments")
        expected = 0
        for segment in segments:
            check_deadline()
            require(type(segment) is list and len(segment) == 3, "segment format")
            lo, hi, value = segment
            require(nat(lo, gas_cap) and nat(hi, gas_cap) and lo == expected and hi >= lo,
                    "non-partitioning gas intervals")
            require(value is None or nat(value), "bound value")
            decoded = math.inf if value is None else value
            for gas in range(lo, hi + 1):
                bounds[locations[qi], x, gas, h] = decoded
            expected = hi + 1
            segment_count += 1
        require(expected == gas_cap + 1, "uncovered gas budget")
    require(len(bounds) == cells, "incomplete bound domain")
    check_deadline()

    obligations = 0
    # Ascending h is convenient but soundness of checking does not depend on it.
    for (q, x, gas, h), lhs in bounds.items():
        check_deadline()
        if q in p["errors"]:
            require(lhs == 0, "nonzero lower bound at error")
        elif h > 0:
            for edge in outgoing[q]:
                check_deadline()
                if not (edge["guard"][0] <= x <= edge["guard"][1] and edge["gas"] <= gas):
                    continue
                update = edge["update"]
                values = range(width) if update == "havoc" else ((update[0] * x + update[1]) % width,)
                for y in values:
                    obligations += 1
                    if obligations > max_work:
                        raise Limit("transition obligation cap")
                    check_deadline()
                    rhs = edge["cost"] + bounds[edge["dst"], y, gas - edge["gas"], h - 1]
                    require(lhs <= rhs, "invalid local lower-bound inequality")
    check_deadline()

    lower = min(bounds[p["start"], x, gas_cap, step_cap] for x in p["initial"])
    if lower == math.inf:
        require(upper is None, "finite witness contradicts infinite lower bound")
        status = "safe_bounded"
    elif upper is None:
        status = "unknown"
    else:
        require(lower <= upper, "bounds contradict witnessed cost")
        status = "optimal_bounded" if lower == upper else "gap_bounded"
    check_deadline()
    return {
        "status": status,
        "lower": None if lower == math.inf else lower,
        "upper": upper,
        "gas": gas_cap,
        "steps": step_cap,
        "cells": cells,
        "segments": segment_count,
        "transition_obligations": obligations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("certificate")
    args = parser.parse_args()
    try:
        result = check_files(args.input, args.certificate)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] in {"optimal_bounded", "safe_bounded", "gap_bounded"} else 2
    except Limit as exc:
        print(json.dumps({"status": "unknown", "reason": str(exc)}, sort_keys=True))
        return 2
    except (Reject, ValueError, OSError, TypeError, KeyError, IndexError,
            RecursionError, UnicodeDecodeError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
