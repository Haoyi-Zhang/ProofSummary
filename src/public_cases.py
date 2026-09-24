"""Exact finite assertion-outcome quotients for six retained SV-COMP sources."""
from __future__ import annotations
from typing import Any
from frontier_cases import edge, program


def _parity_case(name: str, failing_parity: int) -> dict[str, Any]:
    # One exact loop-summary edge preserves parity; x is initially even.
    return program(
        "svcomp-" + name.removesuffix(".c"), ["entry", "assert", "error"],
        [edge(0, "entry", "assert", gas=1, cost=1),
         edge(1, "assert", "error", guard=[failing_parity, failing_parity])],
        gas=1, steps=2, bits=1, initial=[0],
    )


def _threshold_case(name: str, failure_class: int | None) -> dict[str, Any]:
    # Class 0 means final x == T; class 1 means final x > T.
    edges = [edge(0, "entry", "assert", gas=1, cost=1)]
    if failure_class is not None:
        edges.append(edge(1, "assert", "error", guard=[failure_class, failure_class]))
    return program("svcomp-" + name.removesuffix(".c"), ["entry", "assert", "error"],
                   edges, gas=1, steps=2, bits=1, initial=[0, 1])


def public_cases() -> list[tuple[dict[str, Any], str, bool]]:
    # expected_safe is the upstream unreach-call verdict.
    return [
        (_parity_case("simple_1-1.c", 0), "simple_1-1.c", False),
        (_parity_case("simple_1-2.c", 1), "simple_1-2.c", True),
        (_threshold_case("simple_2-1.c", None), "simple_2-1.c", True),
        (_threshold_case("simple_2-2.c", 0), "simple_2-2.c", False),
        (_parity_case("simple_3-1.c", 0), "simple_3-1.c", False),
        (_parity_case("simple_3-2.c", 1), "simple_3-2.c", True),
    ]
