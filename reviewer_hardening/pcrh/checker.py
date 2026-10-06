from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from math import inf
from typing import Any, Mapping

INF_TOKEN = "INF"


class CertificateError(ValueError):
    pass


@dataclass(frozen=True)
class CheckResult:
    valid: bool
    exact_budgets: int
    safe_budgets: int
    gap_budgets: int
    results: dict[int, dict[str, Any]]


class _NoDuplicate(dict):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = _NoDuplicate()
    for key, value in pairs:
        if key in out:
            raise CertificateError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _nat(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CertificateError(f"{name} must be a non-negative integer and not bool")
    return value


def _keys(obj: Any, expected: set[str], name: str, optional: set[str] | None = None) -> None:
    if not isinstance(obj, Mapping):
        raise CertificateError(f"{name} must be an object")
    optional = optional or set()
    actual = set(obj)
    missing = expected - actual
    extra = actual - expected - optional
    if missing or extra:
        raise CertificateError(f"{name} key mismatch: missing={sorted(missing)}, extra={sorted(extra)}")


def _parse_system(obj: Any, name: str) -> dict[str, Any]:
    _keys(obj, {"states", "initial", "errors", "edges", "horizon", "gas_bound"}, name)
    states = obj["states"]
    errors = obj["errors"]
    edges = obj["edges"]
    if not isinstance(states, list) or not states or any(not isinstance(s, str) or not s for s in states):
        raise CertificateError(f"{name}.states invalid")
    if len(states) != len(set(states)):
        raise CertificateError(f"{name}.states contains duplicates")
    state_set = set(states)
    if not isinstance(obj["initial"], str) or obj["initial"] not in state_set:
        raise CertificateError(f"{name}.initial invalid")
    if not isinstance(errors, list) or any(not isinstance(s, str) or s not in state_set for s in errors):
        raise CertificateError(f"{name}.errors invalid")
    if len(errors) != len(set(errors)):
        raise CertificateError(f"{name}.errors contains duplicates")
    if not isinstance(edges, list):
        raise CertificateError(f"{name}.edges invalid")
    parsed_edges: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, edge in enumerate(edges):
        _keys(edge, {"id", "src", "dst", "gas", "cost"}, f"{name}.edges[{index}]")
        if not isinstance(edge["id"], str) or not edge["id"] or edge["id"] in ids:
            raise CertificateError(f"{name}.edges[{index}].id invalid or duplicate")
        ids.add(edge["id"])
        if (not isinstance(edge["src"], str) or not isinstance(edge["dst"], str) or
                edge["src"] not in state_set or edge["dst"] not in state_set):
            raise CertificateError(f"{name}.edges[{index}] endpoint invalid")
        parsed_edges.append({"id": edge["id"], "src": edge["src"], "dst": edge["dst"],
                             "gas": _nat(edge["gas"], "edge.gas"),
                             "cost": _nat(edge["cost"], "edge.cost")})
    return {
        "states": list(states), "state_set": state_set, "initial": obj["initial"],
        "errors": set(errors), "edges": parsed_edges,
        "horizon": _nat(obj["horizon"], f"{name}.horizon"),
        "gas_bound": _nat(obj["gas_bound"], f"{name}.gas_bound"),
    }


def _decode(value: Any, name: str) -> int | float:
    if value == INF_TOKEN:
        return inf
    return _nat(value, name)


def _recompute_table(system: dict[str, Any]) -> list[dict[str, list[int | float]]]:
    outgoing: dict[str, list[dict[str, Any]]] = {s: [] for s in system["states"]}
    for edge in system["edges"]:
        outgoing[edge["src"]].append(edge)
    table: list[dict[str, list[int | float]]] = []
    base: dict[str, list[int | float]] = {}
    for state in system["states"]:
        base[state] = [0 if state in system["errors"] else inf for _ in range(system["gas_bound"] + 1)]
    table.append(base)
    for h in range(1, system["horizon"] + 1):
        layer: dict[str, list[int | float]] = {}
        for state in system["states"]:
            row: list[int | float] = []
            for budget in range(system["gas_bound"] + 1):
                best = 0 if state in system["errors"] else inf
                for edge in outgoing[state]:
                    if edge["gas"] <= budget:
                        suffix = table[h - 1][edge["dst"]][budget - edge["gas"]]
                        if suffix != inf:
                            best = min(best, edge["cost"] + suffix)
                row.append(best)
            layer[state] = row
        table.append(layer)
    return table


def _validate_supplied_table(raw: Any, system: dict[str, Any], expected: list[dict[str, list[int | float]]]) -> None:
    if not isinstance(raw, list) or len(raw) != system["horizon"] + 1:
        raise CertificateError("lower_table has wrong number of layers")
    for h, layer in enumerate(raw):
        if not isinstance(layer, Mapping) or set(layer) != system["state_set"]:
            raise CertificateError(f"lower_table[{h}] state keys invalid")
        for state in system["states"]:
            row = layer[state]
            if not isinstance(row, list) or len(row) != system["gas_bound"] + 1:
                raise CertificateError(f"lower_table[{h}][{state}] width invalid")
            for budget, encoded in enumerate(row):
                actual = _decode(encoded, f"lower_table[{h}][{state}][{budget}]")
                if actual != expected[h][state][budget]:
                    raise CertificateError(f"lower table recurrence mismatch at h={h}, state={state}, budget={budget}")


def _replay(witness: Any, concrete: dict[str, Any], budget: int) -> int:
    _keys(witness, {"budget", "cost", "gas", "steps", "edges"}, f"witness[{budget}]")
    if _nat(witness["budget"], "witness.budget") != budget:
        raise CertificateError("witness budget mismatch")
    if not isinstance(witness["edges"], list) or any(not isinstance(e, str) for e in witness["edges"]):
        raise CertificateError("witness edge list invalid")
    edge_map = {edge["id"]: edge for edge in concrete["edges"]}
    state = concrete["initial"]
    total_gas = 0
    total_cost = 0
    for edge_id in witness["edges"]:
        if state in concrete["errors"]:
            raise CertificateError("witness continues after first error")
        if edge_id not in edge_map:
            raise CertificateError(f"witness references unknown edge {edge_id}")
        edge = edge_map[edge_id]
        if edge["src"] != state:
            raise CertificateError("witness is not path-contiguous")
        state = edge["dst"]
        total_gas += edge["gas"]
        total_cost += edge["cost"]
    if state not in concrete["errors"]:
        raise CertificateError("witness does not end in an error state")
    if len(witness["edges"]) > concrete["horizon"]:
        raise CertificateError("witness exceeds horizon")
    if total_gas > budget:
        raise CertificateError("witness exceeds budget")
    if _nat(witness["cost"], "witness.cost") != total_cost:
        raise CertificateError("witness cost mismatch")
    if _nat(witness["gas"], "witness.gas") != total_gas:
        raise CertificateError("witness gas mismatch")
    if _nat(witness["steps"], "witness.steps") != len(witness["edges"]):
        raise CertificateError("witness step count mismatch")
    return total_cost


def check_certificate_object(cert: Any, *, expected_model_sha256: str | None = None) -> CheckResult:
    _keys(cert, {"schema", "semantics", "concrete", "abstraction", "lower_table", "witnesses", "claims",
                 "untrusted_metrics", "producer_contract"}, "certificate", optional={"model_binding"})
    if cert["schema"] != "pcrh-sandwich-certificate-v1":
        raise CertificateError("unsupported schema")
    concrete = _parse_system(cert["concrete"], "concrete")
    # Legacy retained certificates lack this annotation. A caller-supplied
    # digest is still checked against the complete serialized concrete model.
    digest = hashlib.sha256(json.dumps(cert["concrete"], sort_keys=True,
                                      separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()
    if "model_binding" in cert:
        binding = cert["model_binding"]
        _keys(binding, {"canonical_sha256"}, "model_binding")
        if binding["canonical_sha256"] != digest:
            raise CertificateError("model digest mismatch")
    if expected_model_sha256 is not None and expected_model_sha256 != digest:
        raise CertificateError("external model digest mismatch")
    abstraction = cert["abstraction"]
    _keys(abstraction, {"name", "alpha", "system", "simulation_obligation"}, "abstraction")
    abstract = _parse_system(abstraction["system"], "abstraction.system")
    if concrete["horizon"] != abstract["horizon"] or concrete["gas_bound"] != abstract["gas_bound"]:
        raise CertificateError("concrete/abstract resource bounds differ")
    alpha = abstraction["alpha"]
    if not isinstance(alpha, Mapping) or set(alpha) != concrete["state_set"]:
        raise CertificateError("alpha is not total and exact on concrete states")
    if any(not isinstance(v, str) or v not in abstract["state_set"] for v in alpha.values()):
        raise CertificateError("alpha maps outside abstract state set")
    if set(alpha.values()) != abstract["state_set"]:
        raise CertificateError("abstract system contains unreachable/unmapped blocks")
    if alpha[concrete["initial"]] != abstract["initial"]:
        raise CertificateError("initial state is not preserved")
    if any(alpha[e] not in abstract["errors"] for e in concrete["errors"]):
        raise CertificateError("concrete errors are not covered by abstract errors")
    # Weighted forward simulation: every concrete step has a no-more-expensive abstract representative.
    abstract_edges = abstract["edges"]
    coverage_index: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for ae in abstract_edges:
        coverage_index.setdefault((ae["src"], ae["dst"]), []).append((ae["gas"], ae["cost"]))
    for edge in concrete["edges"]:
        candidates = coverage_index.get((alpha[edge["src"]], alpha[edge["dst"]]), ())
        covered = any(agas <= edge["gas"] and acost <= edge["cost"] for agas, acost in candidates)
        if not covered:
            raise CertificateError(f"uncovered concrete edge: {edge['id']}")
    expected_table = _recompute_table(abstract)
    _validate_supplied_table(cert["lower_table"], abstract, expected_table)
    witnesses = cert["witnesses"]
    claims = cert["claims"]
    if not isinstance(witnesses, Mapping) or not isinstance(claims, Mapping):
        raise CertificateError("witnesses and claims must be objects")
    expected_budget_keys = {str(b) for b in range(concrete["gas_bound"] + 1)}
    if set(claims) != expected_budget_keys or not set(witnesses) <= expected_budget_keys:
        raise CertificateError("budget key set invalid")
    results: dict[int, dict[str, Any]] = {}
    exact = safe = gap = 0
    for budget in range(concrete["gas_bound"] + 1):
        key = str(budget)
        lower = expected_table[abstract["horizon"]][abstract["initial"]][budget]
        witness_cost: int | None = None
        if key in witnesses:
            witness_cost = _replay(witnesses[key], concrete, budget)
        if lower == inf:
            status = "safe"
            safe += 1
            lower_json: int | str = INF_TOKEN
            upper_json: int | str = INF_TOKEN if witness_cost is None else witness_cost
            if witness_cost is not None:
                raise CertificateError("witness contradicts abstract unreachability")
        elif witness_cost is not None and witness_cost == int(lower):
            status = "optimal"
            exact += 1
            lower_json = int(lower)
            upper_json = witness_cost
        else:
            status = "gap"
            gap += 1
            lower_json = int(lower)
            upper_json = INF_TOKEN if witness_cost is None else witness_cost
            if witness_cost is not None and witness_cost < int(lower):
                raise CertificateError("concrete witness violates checked lower bound")
        claim = claims[key]
        _keys(claim, {"status", "lower", "upper"}, f"claims[{key}]")
        _decode(claim["lower"], f"claims[{key}].lower")
        _decode(claim["upper"], f"claims[{key}].upper")
        if claim["status"] != status or claim["lower"] != lower_json or claim["upper"] != upper_json:
            raise CertificateError(f"claim mismatch at budget {budget}")
        results[budget] = {"status": status, "lower": lower_json, "upper": upper_json}
    return CheckResult(True, exact, safe, gap, results)


def check_certificate_bytes(data: bytes) -> CheckResult:
    try:
        obj = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                         parse_constant=lambda token: (_ for _ in ()).throw(CertificateError(f"invalid constant {token}")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CertificateError(f"invalid JSON: {exc}") from exc
    return check_certificate_object(obj)
