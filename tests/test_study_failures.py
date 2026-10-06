"""A rejected dense certificate must fail differential evaluation.

Only Unix RSS sampling and file writes are mocked; the finite producer and
checker computations are real. This test also runs on Windows.
"""
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
if sys.platform == "win32":
    with patch.dict(sys.modules, {"resource": Mock()}):
        study = importlib.import_module("frontier_study")
else:
    study = importlib.import_module("frontier_study")

if sys.platform == "win32":
    with patch.dict(sys.modules, {"resource": Mock()}):
        consumer_study = importlib.import_module("consumer_boundary_study")
else:
    consumer_study = importlib.import_module("consumer_boundary_study")
import mutation_study

from frontier_cases import tradeoff_chain


class StudyFailureTests(unittest.TestCase):
    def run_case(self):
        with patch.object(study, "_write_json"), patch.object(Path, "write_text"):
            return study.run_one(tradeoff_chain(2), "test", "", Path("unused"))

    def test_dense_rejection_is_not_ignored_as_unknown(self):
        with patch.object(study, "check_dense", side_effect=study.DenseCheckReject("false evidence")):
            with self.assertRaises(study.DenseCheckReject):
                self.run_case()

    def test_dense_limit_remains_explicit_unknown(self):
        with patch.object(study, "check_dense", side_effect=study.DenseCheckLimit("work cap")):
            row = self.run_case()
        self.assertEqual("unknown", row["dense_status"])
        self.assertEqual("current-dense-checker-failed", row["dense_evidence"])
        self.assertEqual("optimal_bounded", row["oracle_status"])

    def test_positive_byte_consumer_unknown_is_not_acceptance(self):
        positive = [("case", "frontier", {}, {}, lambda *a, **k: {"status": "unknown"})]
        with patch.object(consumer_study, "positive_cases", return_value=positive), \
                patch.object(consumer_study, "write_bytes"), \
                patch.object(Path, "exists", return_value=False), \
                patch.object(Path, "mkdir"), patch.object(Path, "read_bytes", return_value=b"{}"):
            with self.assertRaises(AssertionError):
                consumer_study.run(Path("unused"))

    def test_mutation_limits_are_unknown_and_fail_the_gate(self):
        p = tradeoff_chain(6)
        certificate, _ = mutation_study.produce(p)
        accepted = mutation_study.check(p, certificate)
        outcomes = [accepted] + [mutation_study.Limit("work cap") for _ in range(21)]
        with patch.object(mutation_study, "check", side_effect=outcomes), \
                patch.object(Path, "exists", return_value=False), patch.object(Path, "mkdir"), \
                patch.object(Path, "write_text"):
            summary = mutation_study.run(Path("unused"))
        self.assertEqual(0, summary["rejected"])
        self.assertTrue(all(row["status"] == "unknown" for row in summary["results"]))
        with patch.object(mutation_study, "run", return_value=summary), \
                patch.object(sys, "argv", ["mutation_study.py", "--out", "unused"]):
            self.assertEqual(1, mutation_study.main())


if __name__ == "__main__":
    unittest.main()
