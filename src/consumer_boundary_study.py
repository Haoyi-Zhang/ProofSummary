"""Bounded byte-consumer replay, separate from function-level experiments.

The retained frontier, dense/interval, micro-language, public-quotient, and
mutation drivers invoke producers and checkers as Python functions.  This study
does not relabel those runs.  Instead it freezes independently serialized query
and certificate byte strings for representative cases, then invokes each
checker's bounded ``check_bytes`` entry.  It also exercises duplicate-key,
byte-cap, and type-sensitive query-binding negatives without allocating large
inputs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import checker as dense_checker
import frontier_checker
import interval_checker
from cases import controls
from frontier_cases import tradeoff_chain
from frontier_producer import produce as produce_frontier
from producer import produce as produce_dense
from public_cases import public_cases
from tiny_exhaustive import program as tiny_program, templates


def encode(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def duplicate_top_level_query(raw: bytes) -> bytes:
    marker = b'{"frontiers":' if raw.startswith(b'{"frontiers":') else b'{"bounds":'
    # Canonical sort order places bounds/frontiers first, not query.  Inject an
    # additional query key immediately after the opening brace; the later
    # original query key is then a duplicate seen by object_pairs_hook.
    if raw.startswith(marker):
        return b'{"query":null,' + raw[1:]
    raise AssertionError("unexpected canonical certificate prefix")


def write_bytes(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)


def positive_cases() -> list[tuple[str, str, dict[str, Any], dict[str, Any], Callable[..., dict[str, Any]]]]:
    result: list[tuple[str, str, dict[str, Any], dict[str, Any], Callable[..., dict[str, Any]]]] = []

    dense_query = controls()[0]
    dense_certificate, _ = produce_dense(dense_query)
    result.append(("dense-control", "dense", dense_query, dense_certificate, dense_checker.check_bytes))
    result.append(("interval-control", "interval", dense_query, dense_certificate,
                   interval_checker.check_bytes))

    frontier_query = tradeoff_chain(4)
    frontier_certificate, _ = produce_frontier(frontier_query)
    result.append(("frontier-stress", "frontier", frontier_query, frontier_certificate,
                   frontier_checker.check_bytes))

    pool = templates()
    micro_query = tiny_program(0, (pool[0],), (0,), 1, 1)
    micro_frontier, _ = produce_frontier(micro_query)
    micro_dense, _ = produce_dense(micro_query)
    result.append(("micro-frontier", "frontier", micro_query, micro_frontier,
                   frontier_checker.check_bytes))
    result.append(("micro-dense", "dense", micro_query, micro_dense,
                   dense_checker.check_bytes))

    for query, source, _expected_safe in public_cases():
        certificate, _ = produce_frontier(query)
        result.append(("public-" + source.removesuffix(".c"), "frontier", query, certificate,
                       frontier_checker.check_bytes))

    mutation_query = tradeoff_chain(6)
    mutation_certificate, _ = produce_frontier(mutation_query)
    # The existing mutation driver remains function-level.  This positive
    # establishes that its unmodified base certificate crosses the bounded
    # byte consumer independently.
    result.append(("mutation-base", "frontier", mutation_query, mutation_certificate,
                   frontier_checker.check_bytes))
    return result


def run(out: Path) -> dict[str, Any]:
    if out.exists():
        raise ValueError("output directory must not exist")
    for folder in ("queries", "certificates", "negative-certificates"):
        (out / folder).mkdir(parents=True, exist_ok=False)

    positives: list[dict[str, Any]] = []
    exemplars: dict[str, tuple[dict[str, Any], dict[str, Any], Callable[..., dict[str, Any]], bytes, bytes]] = {}
    for name, checker_name, query, certificate, consumer in positive_cases():
        query_bytes = encode(query)
        certificate_bytes = encode(certificate)
        query_path = out / "queries" / f"{name}.json"
        certificate_path = out / "certificates" / f"{name}.json"
        write_bytes(query_path, query_bytes)
        write_bytes(certificate_path, certificate_bytes)
        # This call is the evidence: the frozen files are read back, and both
        # byte strings are decoded afresh through a length-bounded,
        # duplicate-key-rejecting consumer entry. Merely writing the files is
        # not counted as a checked replay.
        frozen_query = query_path.read_bytes()
        frozen_certificate = certificate_path.read_bytes()
        result = consumer(frozen_query, frozen_certificate,
                          max_bytes=max(len(frozen_query), len(frozen_certificate)))
        status = result["status"]
        if status not in {"optimal_bounded", "safe_bounded", "gap_bounded"}:
            raise AssertionError("positive consumer encoding was not accepted: " + status)
        positives.append({
            "case": name,
            "checker": checker_name,
            "consumer_entry": "check_bytes",
            "frozen_bytes_read_back": True,
            "status": status,
            "query_bytes": len(query_bytes),
            "certificate_bytes": len(certificate_bytes),
            "query_sha256": digest(query_bytes),
            "certificate_sha256": digest(certificate_bytes),
        })
        exemplars.setdefault(checker_name,
                             (query, certificate, consumer, query_bytes, certificate_bytes))

    negatives: list[dict[str, Any]] = []
    for checker_name in ("frontier", "dense", "interval"):
        query, certificate, consumer, query_bytes, certificate_bytes = exemplars[checker_name]

        duplicate = duplicate_top_level_query(certificate_bytes)
        write_bytes(out / "negative-certificates" / f"{checker_name}-duplicate-key.json", duplicate)
        negative_specs: list[tuple[str, bytes, int]] = [
            ("duplicate-key", duplicate, max(len(query_bytes), len(duplicate))),
            ("byte-cap", certificate_bytes, max(0, len(certificate_bytes) - 1)),
        ]
        bool_certificate = copy.deepcopy(certificate)
        bool_certificate["query"]["bits"] = True
        bool_bytes = encode(bool_certificate)
        write_bytes(out / "negative-certificates" / f"{checker_name}-bool-query.json", bool_bytes)
        negative_specs.append(("bool-query-binding", bool_bytes,
                               max(len(query_bytes), len(bool_bytes))))

        float_certificate = copy.deepcopy(certificate)
        float_certificate["query"]["gas"] = float(query["gas"])
        float_bytes = encode(float_certificate)
        write_bytes(out / "negative-certificates" / f"{checker_name}-float-query.json", float_bytes)
        negative_specs.append(("float-query-binding", float_bytes,
                               max(len(query_bytes), len(float_bytes))))

        for kind, raw, cap in negative_specs:
            try:
                consumer(query_bytes, raw, max_bytes=cap)
                observed = "accepted"
                reason = ""
            except (frontier_checker.Limit, dense_checker.Limit,
                    interval_checker.Limit) as exc:
                observed = "unknown"
                reason = str(exc)
            except (frontier_checker.Reject, dense_checker.Reject,
                    interval_checker.Reject,
                    ValueError, TypeError, UnicodeDecodeError) as exc:
                observed = "rejected"
                reason = str(exc)
            negatives.append({
                "checker": checker_name,
                "negative": kind,
                "consumer_entry": "check_bytes",
                "status": observed,
                "reason": reason,
                "query_sha256": digest(query_bytes),
                "certificate_sha256": digest(raw),
                "max_bytes": cap,
            })

    if any(item["status"] != ("unknown" if item["negative"] == "byte-cap"
                              else "rejected") for item in negatives):
        raise AssertionError("unexpected consumer negative outcome")

    summary = {
        "scope": "representative byte-boundary replay separate from function-level studies",
        "function_level_studies_relabelled": False,
        "positive_cases": len(positives),
        "positive_accepted": len(positives),
        "negative_cases": len(negatives),
        "negative_rejected": sum(item["status"] == "rejected" for item in negatives),
        "negative_unknown": sum(item["status"] == "unknown" for item in negatives),
        "checkers": sorted(exemplars),
        "positive_results": positives,
        "negative_results": negatives,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = run(args.out)
    except (OSError, ValueError, AssertionError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps({key: summary[key] for key in (
        "positive_cases", "positive_accepted", "negative_cases", "negative_rejected",
        "negative_unknown"
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
