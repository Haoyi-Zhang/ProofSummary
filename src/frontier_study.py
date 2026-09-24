"""Run retained experiments for exact budget-parametric frontier certificates.

The regression phase consumes the 661 exact inputs retained by the baseline
study.  The stress phase uses deterministic mathematical families that isolate
frontier width, trace multiplicity, and a gas cap too large for explicit
product expansion.  Standard-library Python only; one worker.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import resource
import time
from typing import Any, Iterable

from frontier_cases import stress_cases
from frontier_checker import Limit, Reject, check
from frontier_oracle import enumerate_frontier
from frontier_producer import Exhausted as FrontierExhausted
from frontier_producer import Unsupported as FrontierUnsupported
from frontier_producer import produce
from model import Exhausted as DenseExhausted
from model import Unsupported as DenseUnsupported
from producer import produce as produce_dense

LEGACY_PHASES = ("interval-pilot", "main", "family", "boundary")
FIELDS = [
    "id", "group", "source_phase", "bits", "locations", "edges", "gas", "steps",
    "theoretical_dense_cells", "status", "cost", "witness_gas", "frontier_rows",
    "frontier_points", "max_frontier_width", "frontier_candidates", "certificate_bytes",
    "dense_status", "dense_cost", "dense_cells", "dense_certificate_bytes",
    "oracle_status", "oracle_cost", "oracle_prefixes", "oracle_error_traces",
    "producer_cpu_s", "checker_cpu_s", "dense_cpu_s", "oracle_cpu_s", "peak_rss_kib",
    "agreement",
]


def _blank() -> dict[str, Any]:
    return {key: "" for key in FIELDS}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def run_one(p: dict[str, Any], group: str, source_phase: str, out: Path,
            *, legacy: dict[str, str] | None = None) -> dict[str, Any]:
    row = _blank()
    row.update(
        id=p["id"], group=group, source_phase=source_phase, bits=p["bits"],
        locations=len(p["locations"]), edges=len(p["edges"]), gas=p["gas"], steps=p["steps"],
        theoretical_dense_cells=(len(p["locations"]) * (1 << p["bits"]) *
                                 (p["gas"] + 1) * (p["steps"] + 1)),
    )
    _write_json(out / "inputs" / f"{p['id']}.json", p)
    started = time.process_time()
    try:
        certificate, producer_stats = produce(p)
    except (FrontierUnsupported, FrontierExhausted) as exc:
        row.update(status="unknown", agreement="incomplete")
        _write_json(out / "details" / f"{p['id']}.json", {"frontier_exception": str(exc)})
        return row
    row["producer_cpu_s"] = time.process_time() - started
    text = json.dumps(certificate, separators=(",", ":")) + "\n"
    (out / "certificates" / f"{p['id']}.json").write_text(text)
    row.update(
        frontier_rows=producer_stats["rows"], frontier_points=producer_stats["points"],
        max_frontier_width=producer_stats["max_points_per_row"],
        frontier_candidates=producer_stats["candidate_pairs"],
        certificate_bytes=len(text.encode()),
    )

    started = time.process_time()
    checked = check(p, certificate)
    row["checker_cpu_s"] = time.process_time() - started
    row.update(status=checked["status"], cost=checked["upper"], witness_gas=checked["witness_gas"])

    dense_result: dict[str, Any]
    started = time.process_time()
    try:
        dense_certificate, dense_stats = produce_dense(p)
        row["dense_cpu_s"] = time.process_time() - started
        dense_text = json.dumps(dense_certificate, separators=(",", ":")) + "\n"
        row.update(
            dense_status=("safe_bounded" if dense_certificate["witness"] is None else "optimal_bounded"),
            dense_cost=(None if dense_certificate["witness"] is None else dense_certificate["witness"]["cost"]),
            dense_cells=dense_stats["cells"], dense_certificate_bytes=len(dense_text.encode()),
        )
        dense_result = {"status": row["dense_status"], "cost": row["dense_cost"],
                        "statistics": dense_stats}
    except (DenseUnsupported, DenseExhausted) as exc:
        row["dense_cpu_s"] = time.process_time() - started
        row["dense_status"] = "unknown"
        dense_result = {"status": "unknown", "reason": str(exc)}

    started = time.process_time()
    oracle = enumerate_frontier(p)
    row["oracle_cpu_s"] = time.process_time() - started
    row.update(
        oracle_status=oracle["status"], oracle_cost=oracle.get("cost"),
        oracle_prefixes=oracle["prefixes"], oracle_error_traces=oracle["error_traces"],
    )

    agreements: list[bool] = []
    if legacy is not None:
        old_cost = None if legacy["oracle_cost"] == "" else int(legacy["oracle_cost"])
        agreements.append((checked["status"], checked["upper"]) ==
                          (legacy["oracle_status"], old_cost))
    if dense_result["status"] != "unknown":
        agreements.append((checked["status"], checked["upper"]) ==
                          (dense_result["status"], dense_result["cost"]))
    if oracle["status"] != "unknown":
        agreements.append((checked["status"], checked["upper"], checked["initial_frontier"]) ==
                          (oracle["status"], oracle["cost"], oracle["frontier"]))
    row["agreement"] = "yes" if all(agreements) else "NO"
    row["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    details = {
        "checker": checked,
        "producer_statistics": producer_stats,
        "dense": dense_result,
        "oracle": oracle,
        "legacy": legacy,
    }
    _write_json(out / "details" / f"{p['id']}.json", details)
    for key in FIELDS:
        if key.endswith("_cpu_s") and isinstance(row[key], float):
            row[key] = format(row[key], ".9f")
    return row


def regression_selection(root: Path) -> Iterable[tuple[dict[str, Any], str, str, dict[str, str]]]:
    seen: set[str] = set()
    for phase in LEGACY_PHASES:
        source = root / phase
        with (source / "raw.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        for old in rows:
            name = old["id"]
            if name in seen:
                raise ValueError("duplicate retained identifier")
            seen.add(name)
            p = json.loads((source / "inputs" / f"{name}.json").read_text())
            yield p, f"legacy-{old['group']}", phase, old


def run_phase(phase: str, out: Path, legacy_root: Path) -> dict[str, Any]:
    if out.exists():
        raise ValueError("output directory must not exist")
    for folder in ("inputs", "certificates", "details"):
        (out / folder).mkdir(parents=True, exist_ok=False)
    if phase == "regression":
        selection = regression_selection(legacy_root)
    else:
        selection = ((p, group, "", None) for p, group in stress_cases())
    started = time.process_time()
    rows: list[dict[str, Any]] = []
    with (out / "raw.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for p, group, source_phase, old in selection:
            row = run_one(p, group, source_phase, out, legacy=old)
            rows.append(row)
            writer.writerow(row)
            stream.flush()
            if row["agreement"] == "NO":
                raise Reject("scientific disagreement: " + p["id"])
    summary = {
        "phase": phase,
        "cases": len(rows),
        "agreement": sum(r["agreement"] == "yes" for r in rows),
        "incomplete": sum(r["agreement"] == "incomplete" for r in rows),
        "oracle_complete": sum(r["oracle_status"] != "unknown" for r in rows),
        "dense_complete": sum(r["dense_status"] != "unknown" for r in rows),
        "cpu_seconds": time.process_time() - started,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "workers": 1,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("regression", "stress"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--legacy-root", type=Path, default=Path("results"))
    args = parser.parse_args()
    try:
        summary = run_phase(args.phase, args.out, args.legacy_root)
    except (OSError, ValueError, KeyError, TypeError, Reject, Limit) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["agreement"] == summary["cases"] and not summary["incomplete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
