"""Independent validation of an abstraction-refinement relation.

A fine abstraction refines a coarse abstraction when the concrete-to-coarse
map factors through the concrete-to-fine map and the coarse abstract system
weighted-simulates the fine abstract system.  This is enough to justify the
pointwise monotonicity of lower bounds without trusting a producer's
"refinement" label.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .checker import CertificateError, check_certificate_object


@dataclass(frozen=True)
class RefinementCheckResult:
    accepted: bool
    fine_states: int
    coarse_states: int
    fine_edges: int
    coarse_edges: int


def _require_dict(obj: Any, label: str) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise CertificateError(f"{label} must be an object")
    return obj


def _require_str_list(obj: Any, label: str) -> list[str]:
    if not isinstance(obj, list) or any(not isinstance(x, str) for x in obj):
        raise CertificateError(f"{label} must be a list of strings")
    if len(set(obj)) != len(obj):
        raise CertificateError(f"{label} contains duplicates")
    return obj


def _edge_tuple(edge: Any, label: str) -> tuple[str, str, int, int]:
    e = _require_dict(edge, label)
    if set(e) != {"id", "src", "dst", "gas", "cost"}:
        raise CertificateError(f"{label} has an invalid key set")
    src, dst, gas, cost = e["src"], e["dst"], e["gas"], e["cost"]
    if not isinstance(src, str) or not isinstance(dst, str):
        raise CertificateError(f"{label} endpoints must be strings")
    if isinstance(gas, bool) or not isinstance(gas, int) or gas < 0:
        raise CertificateError(f"{label} gas must be a nonnegative integer")
    if isinstance(cost, bool) or not isinstance(cost, int) or cost < 0:
        raise CertificateError(f"{label} cost must be a nonnegative integer")
    return src, dst, gas, cost


def _system_view(cert: dict[str, Any]) -> tuple[set[str], set[str], set[str], list[tuple[str, str, int, int]]]:
    key = "abstraction.system"
    abstraction = _require_dict(cert.get("abstraction"), "abstraction")
    system = _require_dict(abstraction.get("system"), key)
    # The certificate schema uses these exact names; checking here is separate
    # from (and in addition to) the full semantic checker.
    states = set(_require_str_list(system.get("states"), f"{key}.states"))
    initial = system.get("initial")
    if not isinstance(initial, str) or initial not in states:
        raise CertificateError(f"{key}.initial is invalid")
    initials = {initial}
    errors = set(_require_str_list(system.get("errors"), f"{key}.errors"))
    raw_edges = system.get("edges")
    if not isinstance(raw_edges, list):
        raise CertificateError(f"{key}.edges must be a list")
    edges = [_edge_tuple(item, f"{key}.edges[{i}]") for i, item in enumerate(raw_edges)]
    return states, initials, errors, edges


def derive_refinement_map(coarse: Mapping[str, Any], fine: Mapping[str, Any]) -> dict[str, str]:
    """Derive the unique factor map from two concrete abstraction maps."""
    coarse_alpha = _require_dict(_require_dict(coarse.get("abstraction"), "coarse.abstraction").get("alpha"), "coarse.alpha")
    fine_alpha = _require_dict(_require_dict(fine.get("abstraction"), "fine.abstraction").get("alpha"), "fine.alpha")
    if set(coarse_alpha) != set(fine_alpha):
        raise CertificateError("coarse and fine alpha domains differ")
    rho: dict[str, str] = {}
    for concrete_state in sorted(fine_alpha):
        fine_state = fine_alpha[concrete_state]
        coarse_state = coarse_alpha[concrete_state]
        if not isinstance(fine_state, str) or not isinstance(coarse_state, str):
            raise CertificateError("alpha values must be strings")
        previous = rho.setdefault(fine_state, coarse_state)
        if previous != coarse_state:
            raise CertificateError("coarse alpha does not factor through fine alpha")
    return rho


def check_refinement_relation(
    coarse: dict[str, Any],
    fine: dict[str, Any],
    *,
    rho: Mapping[str, str] | None = None,
    expected_model_sha256: str | None = None,
) -> RefinementCheckResult:
    """Validate both certificates and the fine-to-coarse simulation."""
    check_certificate_object(coarse, expected_model_sha256=expected_model_sha256)
    check_certificate_object(fine, expected_model_sha256=expected_model_sha256)

    if coarse.get("concrete") != fine.get("concrete"):
        raise CertificateError("refinement certificates contain different concrete systems")

    fine_states, fine_initials, fine_errors, fine_edges = _system_view(fine)
    coarse_states, coarse_initials, coarse_errors, coarse_edges = _system_view(coarse)

    relation = dict(rho) if rho is not None else derive_refinement_map(coarse, fine)
    if set(relation) != fine_states:
        raise CertificateError("refinement map domain is not exactly the fine abstract state set")
    if any(not isinstance(v, str) or v not in coarse_states for v in relation.values()):
        raise CertificateError("refinement map has an invalid coarse target")

    coarse_alpha = coarse["abstraction"]["alpha"]
    fine_alpha = fine["abstraction"]["alpha"]
    if set(coarse_alpha) != set(fine_alpha):
        raise CertificateError("coarse and fine alpha domains differ")
    for state in fine_alpha:
        if relation.get(fine_alpha[state]) != coarse_alpha[state]:
            raise CertificateError("concrete abstraction maps do not factor through refinement map")

    if any(relation[s] not in coarse_initials for s in fine_initials):
        raise CertificateError("fine initial state is not preserved by refinement map")
    if any(relation[s] not in coarse_errors for s in fine_errors):
        raise CertificateError("fine error state is not preserved by refinement map")

    index: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for src, dst, gas, cost in coarse_edges:
        index.setdefault((src, dst), []).append((gas, cost))
    for src, dst, gas, cost in fine_edges:
        choices = index.get((relation[src], relation[dst]), [])
        if not any(cg <= gas and cc <= cost for cg, cc in choices):
            raise CertificateError("coarse abstraction does not weighted-simulate a fine edge")

    return RefinementCheckResult(
        accepted=True,
        fine_states=len(fine_states),
        coarse_states=len(coarse_states),
        fine_edges=len(fine_edges),
        coarse_edges=len(coarse_edges),
    )


__all__ = [
    "RefinementCheckResult",
    "derive_refinement_map",
    "check_refinement_relation",
]
