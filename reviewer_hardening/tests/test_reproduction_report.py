"""Mocked report regression; no numerical study or child program is executed."""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "reproduce.py"
SPEC = importlib.util.spec_from_file_location("supplement_reproduction", SOURCE)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class ReproductionReportTests(unittest.TestCase):
    def invoke(self, root, *, mismatch=None, child_code=0):
        source, output = root / "source", root / "run"
        (source / "results").mkdir(parents=True)
        expected = {"resource": {"status": "passed", "cases": 2},
                    "refinement": {"status": "refinement_audit_passed", "valid": True}}
        for kind, name in (("resource", "resource-attack-summary.json"),
                           ("refinement", "refinement-audit-summary.json")):
            (source / "results" / name).write_text(json.dumps(expected[kind]))

        def core(command):
            target = Path(command[command.index("--out") + 1])
            target.mkdir()
            (target / "reproduction-summary.json").write_text(
                json.dumps({"status": "semantic_reproduction_passed"}))

        def child(command, **kwargs):
            kind = "resource" if "run_resource_attacks.py" in command[1] else "refinement"
            target = Path(command[command.index("--out") + 1])
            target.mkdir()
            name = "resource-attack-summary.json" if kind == "resource" else "refinement-audit-summary.json"
            value = {"status": "changed"} if mismatch == kind else expected[kind]
            (target / name).write_text(json.dumps(value))
            return SimpleNamespace(returncode=child_code)

        with patch.object(runner, "ROOT", source), patch.object(runner, "run", side_effect=core), \
                patch.object(runner.subprocess, "run", side_effect=child), redirect_stdout(io.StringIO()):
            code = runner.main(["--out", str(output)])
        return code, json.loads((output / "reproduction-summary.json").read_text()), expected

    def test_report_keeps_paths_evidence_and_equality_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            code, result, expected = self.invoke(Path(directory))
        self.assertEqual(code, 0)
        self.assertEqual(result, {
            "schema": "pcrh-reviewer-hardening-reproduction-v2",
            "status": "semantic_reproduction_passed",
            "core_summary_relative_path": "core/reproduction-summary.json",
            "resource_attack_summary": expected["resource"],
            "committed_resource_evidence_equal": True,
            "refinement_audit_summary": expected["refinement"],
            "committed_refinement_evidence_equal": True,
        })

    def test_changed_resource_or_refinement_evidence_still_fails(self):
        for kind in ("resource", "refinement"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(SystemExit, "evidence differs from committed result"):
                    self.invoke(Path(directory), mismatch=kind)

    def test_child_failure_still_propagates(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit) as caught:
                self.invoke(Path(directory), child_code=7)
        self.assertEqual(caught.exception.code, 7)


if __name__ == "__main__":
    unittest.main()
