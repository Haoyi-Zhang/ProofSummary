"""Full-scan/archive to outgoing-index/replay inspection compatibility.

This is an evidence comparison, not a certificate checker or timing model.
Only completed recurrence scans have the closed-form counts below. No producer,
checker, successor helper, stored statistic, or certificate supplies the formula.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


def same_json(left: Any, right: Any) -> bool:
    """Exact typed JSON values, ignoring only object order and whitespace."""
    encode = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False)
    return encode(left) == encode(right)


def expected_inspections(query: dict[str, Any]) -> tuple[int, int]:
    """Derive both *completed* recurrence counts from query dimensions.

    h=0 and every error row inspect no edge. At each h=1..H and each
    register value, the full scan inspects all syntactic edges per non-error
    location; the index inspects each edge with a non-error source once.
    Disabled guards, unreachable locations, gas filtering and havoc do not
    alter these counts. Validation, index construction and witness scans are
    outside this counter. This validates formula inputs, not the whole grammar.
    """
    bits, steps = query["bits"], query["steps"]
    locations, errors, edges = query["locations"], query["errors"], query["edges"]
    if (type(bits) is not int or not 1 <= bits <= 6 or
            type(steps) is not int or not 0 <= steps <= 128):
        raise ValueError("inspection formula: bit/step bounds")
    if (type(locations) is not list or not 1 <= len(locations) <= 128 or
            any(type(q) is not str or not q for q in locations) or
            len(set(locations)) != len(locations)):
        raise ValueError("inspection formula: locations")
    if (type(errors) is not list or not errors or
            any(type(q) is not str or q not in locations for q in errors) or
            len(set(errors)) != len(errors)):
        raise ValueError("inspection formula: errors")
    if (type(edges) is not list or len(edges) > 512 or
            any(type(e) is not dict or type(e.get("src")) is not str or
                e["src"] not in locations for e in edges)):
        raise ValueError("inspection formula: edge sources")
    width = 2 ** bits
    if len(locations) * width * (steps + 1) > 200_000:
        raise ValueError("inspection formula: row bound")
    nonerrors = set(locations) - set(errors)
    return (steps * width * len(nonerrors) * len(edges),
            steps * width * sum(e["src"] in nonerrors for e in edges))


@dataclass
class InspectionCompatibility:
    """Explicit one-direction contract; no general statistics exclusion."""
    validated_cases: int = 0
    changed_cases: int = 0

    def compare_details(self, query: dict[str, Any], retained: Any,
                        current: Any, *, complete: bool) -> None:
        if type(retained) is not dict or type(current) is not dict:
            raise ValueError("frontier details must be objects")
        if not complete:
            # run_one emits only an exception, with no partial statistics.
            if (set(retained) != {"frontier_exception"} or
                    not same_json(retained, current)):
                raise ValueError("changed incomplete frontier evidence")
            return
        if set(retained) != set(current) or "producer_statistics" not in retained:
            raise ValueError("changed/missing completed frontier details")
        old, new = retained["producer_statistics"], current["producer_statistics"]
        field = "edge_guard_checks"
        if (type(old) is not dict or type(new) is not dict or set(old) != set(new) or
                field not in old):
            raise ValueError("changed/missing producer statistics")
        full_scan, indexed = expected_inspections(query)
        for label, value, expected in (("retained full-scan", old[field], full_scan),
                                       ("current indexed", new[field], indexed)):
            if type(value) is not int or value != expected:
                raise ValueError(f"{label} inspections: expected {expected}, got {value!r}")
        # Both diagnostics were checked above, including when they agree.
        # Every other producer field and every other detail subtree stays exact.
        for key in retained:
            if key != "producer_statistics":
                if not same_json(retained[key], current[key]):
                    raise ValueError("changed frontier detail field " + key)
            else:
                for statistic in old:
                    if statistic != field and not same_json(old[statistic], new[statistic]):
                        raise ValueError("changed producer statistic " + statistic)
        self.validated_cases += 1
        self.changed_cases += old[field] != new[field]

    def report_fields(self) -> dict[str, Any]:
        """Called by the controller only after all comparisons succeed."""
        return {
            "exact_json_evidence_equal": self.changed_cases == 0,
            "deterministic_count_fields_equal": self.changed_cases == 0,
            "scientific_json_evidence_equal": True,
            "scientific_count_fields_equal": True,
            "frontier_inspection_contract": {
                "field": "details.producer_statistics.edge_guard_checks",
                "retained": "completed-full-edge-scan",
                "current": "completed-outgoing-edge-index",
                "query_validated_cases": self.validated_cases,
                "different_counts": self.changed_cases,
            },
        }
