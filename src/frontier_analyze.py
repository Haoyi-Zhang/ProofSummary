"""Validate retained frontier evidence and export paper-facing derived data."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

PHASES = ("frontier-regression", "frontier-stress")
EXPECTED = {"frontier-regression": 661, "frontier-stress": 14}


def derive(root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    all_rows: list[dict[str, str]] = []
    phase_rows: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for phase in PHASES:
        source = root / phase
        with (source / "raw.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        summary = json.loads((source / "summary.json").read_text())
        if len(rows) != EXPECTED[phase] or summary["cases"] != len(rows):
            raise ValueError(phase + ": selection mismatch")
        if summary["agreement"] != len(rows) or summary["incomplete"]:
            raise ValueError(phase + ": incomplete evidence")
        for row in rows:
            name = row["id"]
            if name in identifiers:
                raise ValueError("duplicate identifier")
            identifiers.add(name)
            p = json.loads((source / "inputs" / f"{name}.json").read_text())
            cpath = source / "certificates" / f"{name}.json"
            c = json.loads(cpath.read_text())
            d = json.loads((source / "details" / f"{name}.json").read_text())
            checked = d["checker"]
            stats = d["producer_statistics"]
            if c["query"] != p or p["id"] != name:
                raise ValueError(name + ": query mismatch")
            if cpath.stat().st_size != int(row["certificate_bytes"]):
                raise ValueError(name + ": certificate byte mismatch")
            pairs = [(row["status"], row["cost"]),
                     (checked["status"], "" if checked["upper"] is None else str(checked["upper"]))]
            if pairs[0] != pairs[1] or row["agreement"] != "yes":
                raise ValueError(name + ": result mismatch")
            for field, expected in (
                ("frontier_rows", stats["rows"]), ("frontier_points", stats["points"]),
                ("max_frontier_width", stats["max_points_per_row"]),
                ("frontier_candidates", stats["candidate_pairs"]),
            ):
                if int(row[field]) != expected:
                    raise ValueError(name + ": changed " + field)
            oracle = d["oracle"]
            if oracle["status"] != "unknown":
                if (checked["status"], checked["upper"], checked["initial_frontier"]) != (
                        oracle["status"], oracle["cost"], oracle["frontier"]):
                    raise ValueError(name + ": oracle mismatch")
        statuses = Counter(r["status"] for r in rows)
        phase_rows.append({
            "phase": phase, "cases": len(rows), "optimal": statuses["optimal_bounded"],
            "safe": statuses["safe_bounded"],
            "oracle_complete": summary["oracle_complete"],
            "dense_current_checked": summary["dense_current_checked"],
            "dense_legacy_checked_records": summary["dense_legacy_checked_records"],
            "dense_unknown": summary["dense_unknown"],
            "frontier_points": sum(int(r["frontier_points"]) for r in rows),
            "frontier_candidates": sum(int(r["frontier_candidates"]) for r in rows),
            "dense_cells": sum(int(r["dense_cells"]) for r in rows if r["dense_cells"]),
            "cpu_seconds": summary["cpu_seconds"], "peak_rss_kib": summary["peak_rss_kib"],
        })
        all_rows.extend(rows)
    regression = [r for r in all_rows if r["source_phase"]]
    stress = [r for r in all_rows if not r["source_phase"]]
    totals: dict[str, Any] = {
        "cases": len(all_rows), "regression_cases": len(regression), "stress_cases": len(stress),
        "phase_rows": phase_rows,
        "regression_mismatches": sum(r["agreement"] != "yes" for r in regression),
        "regression_max_frontier_width": max(int(r["max_frontier_width"]) for r in regression),
        "regression_frontier_points": sum(int(r["frontier_points"]) for r in regression),
        "regression_frontier_candidates": sum(int(r["frontier_candidates"]) for r in regression),
        "stress_oracle_unknown": sum(r["oracle_status"] == "unknown" for r in stress),
        "stress_dense_unknown": sum(r["dense_status"] == "unknown" for r in stress),
        "largest_gas_cap": max(int(r["gas"]) for r in all_rows),
        "largest_theoretical_dense_cells": max(int(r["theoretical_dense_cells"]) for r in all_rows),
    }
    tradeoffs = sorted((r for r in stress if r["group"] == "linear-width-worst-case"),
                       key=lambda r: int(r["steps"]))
    dominated = sorted((r for r in stress if r["group"] == "exponential-traces-collapsed"),
                        key=lambda r: int(r["steps"]))
    totals["tradeoff_widths"] = [[int(r["steps"]), int(r["max_frontier_width"])] for r in tradeoffs]
    totals["dominated_widths"] = [[int(r["steps"]), int(r["max_frontier_width"])] for r in dominated]
    totals["large_gas_cases"] = [r["id"] for r in stress if int(r["gas"]) == 1_000_000]
    return totals, all_rows


def export(root: Path, out: Path, paper: Path | None = None) -> dict[str, Any]:
    metrics, rows = derive(root)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    with (out / "stress-summary.csv").open("w", newline="") as stream:
        fields = ["id", "group", "gas", "steps", "theoretical_dense_cells", "frontier_rows",
                  "frontier_points", "max_frontier_width", "frontier_candidates", "dense_status",
                  "oracle_status", "oracle_prefixes"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: r[field] for field in fields} for r in rows if not r["source_phase"])
    if paper is not None:
        paper.mkdir(parents=True, exist_ok=True)
        (paper / "frontier-stress.csv").write_bytes((out / "stress-summary.csv").read_bytes())
        lines = ["% Generated by artifact/src/frontier_analyze.py."]
        labels = {"frontier-regression": "Retained-input regression", "frontier-stress": "Stress families"}
        for p in metrics["phase_rows"]:
            dense_evidence = (f"current {p['dense_current_checked']:,}; "
                              f"retained {p['dense_legacy_checked_records']:,}; "
                              f"producer unknown {p['dense_unknown']:,}")
            lines.append(
                f"{labels[p['phase']]} & {p['cases']:,} & {p['optimal']:,} & "
                f"{p['safe']:,} & {p['oracle_complete']:,} & {dense_evidence} & "
                f"{p['frontier_points']:,} \\\\"
            )
        (paper / "frontier-phase-rows.tex").write_text("\n".join(lines) + "\n")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--paper-out", type=Path)
    args = parser.parse_args()
    try:
        metrics = export(args.results, args.out, args.paper_out)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "inconsistent", "reason": str(exc)}))
        return 1
    print(json.dumps({"status": "reconciled", "cases": metrics["cases"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
