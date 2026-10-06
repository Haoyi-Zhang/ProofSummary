"""Resource-bounded entry point for the independent certificate checker.

The semantic checker in :mod:`pcrh.checker` is intentionally small and mirrors
only the proof rules.  This module adds a fail-closed resource envelope before
semantic checking so malformed or adversarial JSON cannot request unbounded
work merely by claiming enormous tables or integers.

It imports the checker only; it never imports the producer, search engine, or
abstraction builder.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .checker import CertificateError, CheckResult, check_certificate_object


@dataclass(frozen=True)
class CheckerLimits:
    max_certificate_bytes: int = 16 * 1024 * 1024
    max_json_depth: int = 64
    max_total_nodes: int = 2_000_000
    max_list_items: int = 1_000_000
    max_dict_items: int = 100_000
    max_string_bytes: int = 4 * 1024 * 1024
    max_integer_abs: int = (1 << 63) - 1
    max_table_cells: int = 200_000
    max_transition_visits: int = 200_000


DEFAULT_LIMITS = CheckerLimits()


class ResourceEnvelopeError(CertificateError):
    """Raised when an input exceeds the checker resource envelope."""


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ResourceEnvelopeError(f"duplicate JSON key: {key!r}")
        out[key] = value
    return out


def _reject_constant(token: str) -> Any:
    raise ResourceEnvelopeError(f"non-finite JSON numeric constant: {token}")


def _validate_envelope(value: Any, limits: CheckerLimits) -> None:
    # Iterative traversal avoids making Python recursion depth part of the
    # certificate's attack surface.
    stack: list[tuple[Any, int]] = [(value, 0)]
    seen_nodes = 0
    while stack:
        node, depth = stack.pop()
        seen_nodes += 1
        if seen_nodes > limits.max_total_nodes:
            raise ResourceEnvelopeError("JSON node count exceeds checker limit")
        if depth > limits.max_json_depth:
            raise ResourceEnvelopeError("JSON nesting depth exceeds checker limit")

        if node is None or isinstance(node, bool):
            # Bool-versus-int discipline is enforced by the semantic checker.
            continue
        if isinstance(node, int):
            if abs(node) > limits.max_integer_abs:
                raise ResourceEnvelopeError("integer exceeds checker limit")
            continue
        if isinstance(node, float):
            # The certificate schema has no floating-point fields.  Rejecting
            # here is both simpler and avoids implementation-dependent values.
            raise ResourceEnvelopeError("floating-point values are not allowed")
        if isinstance(node, str):
            if len(node.encode("utf-8")) > limits.max_string_bytes:
                raise ResourceEnvelopeError("string exceeds checker limit")
            continue
        if isinstance(node, list):
            if len(node) > limits.max_list_items:
                raise ResourceEnvelopeError("list length exceeds checker limit")
            stack.extend((item, depth + 1) for item in node)
            continue
        if isinstance(node, dict):
            if len(node) > limits.max_dict_items:
                raise ResourceEnvelopeError("object size exceeds checker limit")
            for key, item in node.items():
                if not isinstance(key, str):
                    raise ResourceEnvelopeError("JSON object key is not a string")
                if len(key.encode("utf-8")) > limits.max_string_bytes:
                    raise ResourceEnvelopeError("object key exceeds checker limit")
                stack.append((item, depth + 1))
            continue
        raise ResourceEnvelopeError(f"unsupported decoded JSON value: {type(node).__name__}")


def _bound_semantic_work(value: dict[str, Any], limits: CheckerLimits) -> None:
    """Bound the table requested by scalar dimensions, not just JSON nodes.

    Malformed dimensions are left for the semantic schema checker. Valid
    integer dimensions cannot cause a huge allocation before a shape check.
    Transition visits conservatively include syntactic error-source edges.
    """
    abstraction = value.get("abstraction")
    if not isinstance(abstraction, dict):
        return
    system = abstraction.get("system")
    if not isinstance(system, dict):
        return
    states, edges = system.get("states"), system.get("edges")
    horizon, gas = system.get("horizon"), system.get("gas_bound")
    if (not isinstance(states, list) or not isinstance(edges, list) or
            type(horizon) is not int or type(gas) is not int or horizon < 0 or gas < 0):
        return
    if len(states) * (horizon + 1) * (gas + 1) > limits.max_table_cells:
        raise ResourceEnvelopeError("requested semantic table exceeds checker limit")
    # The recurrence loops over each syntactic edge at every gas and step
    # layer, even when the charge is too high to use that edge.
    if horizon * (gas + 1) * len(edges) > limits.max_transition_visits:
        raise ResourceEnvelopeError("requested semantic transition visits exceed checker limit")


def check_certificate_bytes_bounded(
    payload: bytes,
    *,
    expected_model_sha256: str | None = None,
    limits: CheckerLimits = DEFAULT_LIMITS,
) -> CheckResult:
    """Parse and check a certificate under explicit fail-closed limits."""
    if not isinstance(payload, (bytes, bytearray)):
        raise ResourceEnvelopeError("certificate payload must be bytes")
    if len(payload) > limits.max_certificate_bytes:
        raise ResourceEnvelopeError("certificate byte length exceeds checker limit")
    try:
        text = bytes(payload).decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ResourceEnvelopeError("certificate is not valid UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except ResourceEnvelopeError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ResourceEnvelopeError("certificate is not valid strict JSON within the parser envelope") from exc
    _validate_envelope(value, limits)
    if not isinstance(value, dict):
        raise ResourceEnvelopeError("certificate top level must be an object")
    _bound_semantic_work(value, limits)
    return check_certificate_object(
        value,
        expected_model_sha256=expected_model_sha256,
    )


__all__ = [
    "CheckerLimits",
    "DEFAULT_LIMITS",
    "ResourceEnvelopeError",
    "check_certificate_bytes_bounded",
]
