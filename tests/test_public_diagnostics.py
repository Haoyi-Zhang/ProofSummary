"""Public quotient diagnostic compatibility; finite, portable, no measurements.

Frozen inputs/results are read-only. Fresh results use the current public replay.
Independent inspection-site/path enumeration is test-local, not copied history.
The inherited Windows resource shim is import-only; no controller child is run.
"""
import ast
import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_frontier_diagnostics as diagnostics
import test_outgoing_index as owned
from frontier_diagnostics import InspectionCompatibility, same_json
from frontier_oracle import enumerate_frontier
import mutation_study
import public_replay

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results" / "public-summary-cases"


def public_records():
    with (SOURCE / "raw.csv").open(newline="") as stream:
        selected = list(csv.DictReader(stream))
    records = []
    for row in selected:
        query = json.loads((SOURCE / "inputs" / (row["id"] + ".json")).read_text())
        actual = owned.capture(query)
        oracle = enumerate_frontier(query)
        current = dict(checker=actual["checker"], oracle=oracle,
                       producer_statistics=actual["statistics"], source=row["source"],
                       expected_safe=row["expected_safe"] == "true")
        retained = json.loads((SOURCE / "details" / (row["id"] + ".json")).read_text())
        inspections = diagnostics.enumerated_inspections(query)
        assert inspections == (retained["producer_statistics"]["edge_guard_checks"],
                               current["producer_statistics"]["edge_guard_checks"])
        InspectionCompatibility().compare_details(query, retained, current, complete=True)
        for stored_row in actual["certificate"]["frontiers"]:
            qi, x, h, front = stored_row
            assert tuple(map(tuple, front)) == owned.independent_front(query, query["locations"][qi], x, h)
        frozen = (SOURCE / "certificates" / (row["id"] + ".json")).read_bytes()
        # Public replay compares decoded typed JSON, not object insertion order.
        assert same_json(json.loads(frozen), actual["certificate"])
        boundary = ROOT / "results" / "consumer-boundary"
        name = "public-" + row["source"].removesuffix(".c") + ".json"
        def canonical(value):
            return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        assert (boundary / "queries" / name).read_bytes() == canonical(query)
        assert (boundary / "certificates" / name).read_bytes() == canonical(actual["certificate"])
        records.append(dict(query=query, certificate=actual["certificate"],
                            details=current, inspections=list(inspections)))
    assert len(records) == 6
    return records


def mutation_summary():
    with tempfile.TemporaryDirectory() as directory:
        result = mutation_study.run(Path(directory) / "new")
    retained = json.loads((ROOT / "results" / "frontier-mutations" / "summary.json").read_text())
    assert same_json(retained, result)
    return result


def snapshot():
    """Actual before/current workers keep the inspection diagnostic visible."""
    # Unlike public_records, this snapshot permits either scan mode so the
    # private comparator can apply the independently validated contract later.
    with (SOURCE / "raw.csv").open(newline="") as stream:
        selection = list(csv.DictReader(stream))
    records = []
    for row in selection:
        query = json.loads((SOURCE / "inputs" / (row["id"] + ".json")).read_text())
        actual = owned.capture(query)
        records.append(dict(query=query, actual=actual, oracle=enumerate_frontier(query)))
    return dict(public=records, mutations=mutation_summary())


class PublicDiagnosticTests(unittest.TestCase):
    def test_frozen_six_and_actual_public_consumer(self):
        records = public_records()
        self.assertEqual(sum(r["details"]["expected_safe"] for r in records), 3)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "new"
            with patch.object(sys, "argv", ["public_replay", "--source", str(SOURCE), "--out", str(out)]), \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(public_replay.main(), 0)
            contract = InspectionCompatibility()
            self.assertEqual(diagnostics.reproduce.compare(SOURCE, out, frontier_inspections=contract), 6)
            self.assertEqual((contract.validated_cases, contract.changed_cases), (6, 6))
            self.assertFalse(contract.report_fields()["exact_json_evidence_equal"])
            with self.assertRaises(ValueError):
                diagnostics.reproduce.compare(SOURCE, out)
            # The exact controller wire must opt in; this test does not run its
            # POSIX-only whole campaign or infer success from an existing report.
            tree = ast.parse((ROOT / "reproduce.py").read_text())
            calls = [node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "public_compared" for t in node.targets)]
            self.assertEqual(len(calls), 1)
            self.assertTrue(any(k.arg == "frontier_inspections" and isinstance(k.value, ast.Name)
                                and k.value.id == "frontier_inspections" for k in calls[0].keywords))

    def test_every_typed_public_field_and_both_diagnostics_reject_changes(self):
        def leaves(value, path=()):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield from leaves(child, path + (key,))
            elif isinstance(value, list):
                for key, child in enumerate(value):
                    yield from leaves(child, path + (key,))
            else:
                yield path, value
        for record in public_records():
            query, current = record["query"], record["details"]
            retained = json.loads((SOURCE / "details" / (query["id"] + ".json")).read_text())
            for side in (0, 1):
                for path, old in leaves((retained, current)[side]):
                    changes = [int(old)] if type(old) is bool else [float(old), old + 1] if type(old) is int else ["changed"]
                    for changed in changes:
                        pair = copy.deepcopy((retained, current))
                        parent = pair[side]
                        for key in path[:-1]:
                            parent = parent[key]
                        parent[path[-1]] = changed
                        with self.subTest(query=query["id"], side=side, path=path, value=changed), self.assertRaises(ValueError):
                            InspectionCompatibility().compare_details(query, *pair, complete=True)
            pair = copy.deepcopy((retained, current))
            for detail in pair:
                detail["producer_statistics"]["edge_guard_checks"] = 999
            with self.assertRaises(ValueError):
                InspectionCompatibility().compare_details(query, *pair, complete=True)
            with self.assertRaises(ValueError):
                InspectionCompatibility().compare_details(query, retained, current, complete=False)

    def test_mutation_summary_all_fields_and_rejections_unchanged(self):
        summary = mutation_summary()
        self.assertEqual((summary["mutations"], summary["rejected"], summary["accepted"]), (21, 21, 0))


if __name__ == "__main__":
    unittest.main()
