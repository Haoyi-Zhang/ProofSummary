#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

VOLATILE_KEYS = {"elapsed_seconds_untrusted"}


def run(command: list[str], cwd: Path, log: Path, env: dict[str, str] | None = None) -> None:
    merged = dict(os.environ)
    merged.pop("PYTHONPATH", None)
    if env:
        merged.update(env)
    with log.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(command, cwd=cwd, env=merged, stdout=handle, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-80:])
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(command)}\n{tail}")


def canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items()) if k not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    out = args.out.resolve()
    if out.exists():
        raise SystemExit(f"refusing existing output directory: {out}")
    out.mkdir(parents=True)
    work = out / "work"
    shutil.copytree(source, work, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    logs = out / "logs"
    logs.mkdir()
    python = sys.executable
    run([python, "-m", "unittest", "discover", "-s", "tests", "-v"], work, logs / "unit.log", {"PYTHONPATH": "."})
    run([python, "scripts/run_mutations.py"], work, logs / "mutations.log", {"PYTHONPATH": "."})
    run([python, "scripts/run_fuzz.py"], work, logs / "fuzz.log", {"PYTHONPATH": "."})
    run([python, "scripts/run_exhaustive.py"], work, logs / "exhaustive.log", {"PYTHONPATH": "."})

    # Dynamic independence check: execute the checker with no producer/core module present.
    checker_only = out / "checker-only"
    package = checker_only / "pcrh"
    package.mkdir(parents=True)
    shutil.copy2(work / "pcrh" / "checker.py", package / "checker.py")
    shutil.copy2(work / "pcrh" / "standalone_checker.py", package / "standalone_checker.py")
    (package / "__init__.py").write_text("from .checker import *\n", encoding="utf-8")
    shutil.copy2(work / "certificates" / "coarse-gap.json", checker_only / "coarse-gap.json")
    run([python, "-m", "pcrh.standalone_checker", "coarse-gap.json"], checker_only,
        logs / "checker-only.log", {"PYTHONPATH": "."})

    names = ["exhaustive-summary.json", "fuzz-summary.json", "mutation-summary.json"]
    equality = {}
    for name in names:
        embedded = json.loads((source / "results" / name).read_text(encoding="utf-8"))
        reproduced = json.loads((work / "results" / name).read_text(encoding="utf-8"))
        same = canonical(embedded) == canonical(reproduced)
        equality[name] = same
        if not same:
            raise RuntimeError(f"semantic result differs: {name}")
    raw_equal = sha256(source / "results" / "exhaustive-queries.csv") == sha256(work / "results" / "exhaustive-queries.csv")
    if not raw_equal:
        raise RuntimeError("raw exhaustive CSV is not deterministic")
    exhaustive = json.loads((work / "results" / "exhaustive-summary.json").read_text(encoding="utf-8"))
    fuzz = json.loads((work / "results" / "fuzz-summary.json").read_text(encoding="utf-8"))
    mutations = json.loads((work / "results" / "mutation-summary.json").read_text(encoding="utf-8"))
    summary = {
        "status": "semantic_reproduction_passed",
        "exhaustive_queries": exhaustive["enumeration"]["queries"],
        "checker_budget_results": exhaustive["enumeration"]["checker_budget_results"],
        "random_systems": fuzz["systems"],
        "random_budget_queries": fuzz["budget_queries"],
        "hard_mutation_rejections": mutations["hard_rejections"],
        "checker_only_execution": True,
        "semantic_json_equal": equality,
        "raw_csv_equal": raw_equal,
        "python": sys.version,
    }
    (out / "reproduction-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
