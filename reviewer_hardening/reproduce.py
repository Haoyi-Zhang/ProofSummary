#!/usr/bin/env python3
"""Reproduce the core hardening study plus the fail-closed parser envelope."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode:
        raise SystemExit(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--out", required=True, type=Path)
    args, extra = parser.parse_known_args(argv)
    out = args.out.resolve()
    if out.exists():
        raise SystemExit(f"refusing existing output directory: {out}")
    out.mkdir(parents=True)

    core_out = out / "core"
    run([sys.executable, str(ROOT / "reproduce_core.py"), "--out", str(core_out), *extra])

    resource_out = out / "resource-attacks"
    env_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_resource_attacks.py"),
        "--out",
        str(resource_out),
    ]
    proc = subprocess.run(env_cmd, cwd=ROOT, env={**__import__("os").environ, "PYTHONPATH": str(ROOT)})
    if proc.returncode:
        raise SystemExit(proc.returncode)

    generated = resource_out / "resource-attack-summary.json"
    committed = ROOT / "results" / "resource-attack-summary.json"
    generated_obj = json.loads(generated.read_text())
    committed_obj = json.loads(committed.read_text())
    if generated_obj != committed_obj:
        raise SystemExit("resource attack evidence differs from committed result")

    refinement_out = out / "refinement-audit"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_refinement_audit.py"), "--out", str(refinement_out)],
        cwd=ROOT,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT)},
    )
    if proc.returncode:
        raise SystemExit(proc.returncode)
    refinement_generated = refinement_out / "refinement-audit-summary.json"
    refinement_committed = ROOT / "results" / "refinement-audit-summary.json"
    refinement_obj = json.loads(refinement_generated.read_text())
    if refinement_obj != json.loads(refinement_committed.read_text()):
        raise SystemExit("refinement audit evidence differs from committed result")

    core_summaries = sorted(core_out.rglob("reproduction-summary.json"))
    if not core_summaries:
        raise SystemExit("core reproduction summary missing")
    core_summary_path = core_summaries[-1]
    core_summary = json.loads(core_summary_path.read_text())
    if "passed" not in json.dumps(core_summary, sort_keys=True):
        raise SystemExit("core reproduction did not report a passing status")

    result = {
        "schema": "pcrh-reviewer-hardening-reproduction-v2",
        "status": "semantic_reproduction_passed",
        "core_summary_relative_path": core_summary_path.relative_to(out).as_posix(),
        "core_summary_sha256": sha256(core_summary_path),
        "resource_attack_summary": generated_obj,
        "resource_attack_summary_sha256": sha256(generated),
        "committed_resource_evidence_equal": True,
        "refinement_audit_summary": refinement_obj,
        "refinement_audit_summary_sha256": sha256(refinement_generated),
        "committed_refinement_evidence_equal": True,
    }
    (out / "reproduction-summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
