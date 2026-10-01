"""Replay a retained frontier study from exact inputs and compare evidence."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import resource
import time

from frontier_study import FIELDS, run_one


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("output directory must not exist")
    for folder in ("inputs", "certificates", "dense-certificates", "details"):
        (args.out / folder).mkdir(parents=True, exist_ok=False)
    with (args.source / "raw.csv").open(newline="") as stream:
        selection = list(csv.DictReader(stream))
    started = time.process_time()
    rows = []
    with (args.out / "raw.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for selected in selection:
            name = selected["id"]
            p = json.loads((args.source / "inputs" / f"{name}.json").read_text())
            legacy = None
            retained_detail = json.loads((args.source / "details" / f"{name}.json").read_text())
            if retained_detail.get("legacy") is not None:
                legacy = retained_detail["legacy"]
            row = run_one(p, selected["group"], selected["source_phase"], args.out,
                          legacy=legacy)
            rows.append(row)
            writer.writerow(row)
            if row["agreement"] == "NO":
                raise SystemExit("scientific disagreement: " + name)
    old_summary = json.loads((args.source / "summary.json").read_text())
    summary = {
        "phase": old_summary["phase"], "cases": len(rows),
        "agreement": sum(r["agreement"] == "yes" for r in rows),
        "incomplete": sum(r["agreement"] == "incomplete" for r in rows),
        "oracle_complete": sum(r["oracle_status"] != "unknown" for r in rows),
        "dense_current_checked": sum(r["dense_evidence"] == "current-independent-dense-checker" for r in rows),
        "dense_legacy_checked_records": sum(r["dense_evidence"] == "retained-legacy-dense-and-interval-check-record" for r in rows),
        "dense_unknown": sum(r["dense_status"] == "unknown" for r in rows),
        "cpu_seconds": time.process_time() - started,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "workers": 1,
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["agreement"] == summary["cases"] and not summary["incomplete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
