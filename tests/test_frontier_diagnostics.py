"""Portable finite diagnostic-contract tests, not a Linux campaign.

Owned queries/current production are reused from the outgoing-index regression.
The old scan count is derived by test-local iteration, not old implementation
code. Unix resource is stubbed only to import the comparison controller; no
resource sampler, child invocation, measurement, or full controller is run.
"""
from __future__ import annotations

import copy
import csv
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import test_outgoing_index as owned
from frontier_diagnostics import InspectionCompatibility, expected_inspections

if sys.platform == "win32":
    with patch.dict(sys.modules, {"resource": Mock()}):
        reproduce = importlib.import_module("reproduce")
else:
    import reproduce


def enumerated_inspections(query):
    """Independent traversal of inspection sites, without a closed formula."""
    full = indexed = 0
    for remaining in range(query["steps"] + 1):
        for location in query["locations"]:
            for _value in range(2 ** query["bits"]):
                if remaining == 0 or location in query["errors"]:
                    continue
                for transition in query["edges"]:
                    full += 1
                    if transition["src"] == location:
                        indexed += 1
    return full, indexed


def examples():
    result = owned.fixtures()
    result.append(owned.query("diagnostic_empty", ["s", "z"], [], 0, 0))
    multi = owned.query("diagnostic_multi_error", ["s", "dead", "a", "z"],
                        [owned.edge(0, "s", "a", guard=(1, 1)),
                         owned.edge(1, "a", "z"), owned.edge(2, "z", "s"),
                         owned.edge(3, "dead", "z")], 0, 2)
    multi["errors"] = ["a", "z"]
    result.append(multi)
    return result


def details(query):
    actual = owned.capture(query)
    current = {"producer_statistics": actual["statistics"], "checker": actual["checker"],
               "dense": {"status": "owned-control", "cost": None},
               "oracle": {"frontier": actual["checker"]["initial_frontier"]},
               "legacy": None}
    retained = copy.deepcopy(current)
    full, indexed = enumerated_inspections(query)
    assert current["producer_statistics"]["edge_guard_checks"] == indexed
    retained["producer_statistics"]["edge_guard_checks"] = full
    return retained, current, actual["certificate"]


def write_evidence(target, query, detail, certificate, row):
    for folder in ("inputs", "certificates", "dense-certificates", "details"):
        (target / folder).mkdir(parents=True, exist_ok=False)
    for folder, value in (("inputs", query), ("details", detail)):
        (target / folder / (query["id"] + ".json")).write_text(json.dumps(value))
    if certificate is not None:
        (target / "certificates" / (query["id"] + ".json")).write_text(json.dumps(certificate))
    with (target / "raw.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)


class DiagnosticCompatibilityTests(unittest.TestCase):
    def test_both_counts_from_independent_iteration_and_actual_production(self):
        contract = InspectionCompatibility()
        differences = 0
        for query in examples():
            old, new, _ = details(query)
            full, indexed = enumerated_inspections(query)
            self.assertEqual((full, indexed), expected_inspections(query))
            self.assertEqual(full, old["producer_statistics"]["edge_guard_checks"])
            self.assertEqual(indexed, new["producer_statistics"]["edge_guard_checks"])
            contract.compare_details(query, old, new, complete=True)
            differences += full != indexed
        self.assertEqual(len(examples()), contract.validated_cases)
        self.assertEqual(differences, contract.changed_cases)

    def test_wrong_retained_or_current_counts_reject_even_equal_corruptions(self):
        for query in (examples()[0], examples()[-1], examples()[-2], examples()[5]):
            old, new, _ = details(query)
            for side in (0, 1):
                for wrong in (-1, True, 0.0, "0", None,
                              (old, new)[side]["producer_statistics"]["edge_guard_checks"] + 1):
                    pair = copy.deepcopy((old, new))
                    pair[side]["producer_statistics"]["edge_guard_checks"] = wrong
                    with self.subTest(query=query["id"], side=side, wrong=wrong):
                        with self.assertRaises(ValueError):
                            InspectionCompatibility().compare_details(query, *pair, complete=True)
            pair = copy.deepcopy((old, new))
            for item in pair:
                item["producer_statistics"]["edge_guard_checks"] = 999
            with self.assertRaises(ValueError):
                InspectionCompatibility().compare_details(query, *pair, complete=True)

    def test_every_other_statistic_and_detail_subtree_stays_exact(self):
        query = examples()[0]
        old, new, _ = details(query)
        for key in new["producer_statistics"]:
            if key == "edge_guard_checks":
                continue
            changed = copy.deepcopy(new)
            changed["producer_statistics"][key] += 1
            with self.subTest(statistic=key), self.assertRaises(ValueError):
                InspectionCompatibility().compare_details(query, old, changed, complete=True)
        for key in ("checker", "dense", "oracle", "legacy"):
            changed = copy.deepcopy(new)
            changed[key] = {"changed_science": True}
            with self.subTest(subtree=key), self.assertRaises(ValueError):
                InspectionCompatibility().compare_details(query, old, changed, complete=True)
        for wrong in (True, 480.0):
            changed = copy.deepcopy(new)
            changed["producer_statistics"]["candidate_pairs"] = wrong
            with self.assertRaises(ValueError):
                InspectionCompatibility().compare_details(query, old, changed, complete=True)
        changed = copy.deepcopy(new)
        changed["checker"]["edge_guard_checks"] += 1
        with self.assertRaises(ValueError):
            InspectionCompatibility().compare_details(query, old, changed, complete=True)

    def test_missing_or_added_scientific_fields_reject(self):
        query = examples()[0]
        old, new, _ = details(query)
        for key in ("producer_statistics", "checker"):
            changed = copy.deepcopy(new)
            del changed[key]
            with self.assertRaises(ValueError):
                InspectionCompatibility().compare_details(query, old, changed, complete=True)
        for action in ("missing_inspections", "extra_statistic"):
            changed = copy.deepcopy(new)
            if action == "missing_inspections":
                del changed["producer_statistics"]["edge_guard_checks"]
            else:
                changed["producer_statistics"]["unrecognized"] = 0
            with self.assertRaises(ValueError):
                InspectionCompatibility().compare_details(query, old, changed, complete=True)

    def test_incomplete_results_have_only_exact_exception_evidence(self):
        query = examples()[0]
        unknown = {"frontier_exception": "frontier candidate limit"}
        contract = InspectionCompatibility()
        contract.compare_details(query, unknown, copy.deepcopy(unknown), complete=False)
        self.assertEqual(0, contract.validated_cases)
        for changed in ({"frontier_exception": "frontier CPU limit"},
                        {**unknown, "producer_statistics": {"edge_guard_checks": 0}}):
            with self.assertRaises(ValueError):
                contract.compare_details(query, unknown, changed, complete=False)

    def test_formula_dimensions_and_error_sources_are_validated(self):
        query = examples()[-1]
        for field, value in (("bits", True), ("steps", 1.0), ("steps", -1),
                             ("errors", ["unknown"]), ("errors", ["a", "a"]),
                             ("locations", ["s", "s"])):
            changed = copy.deepcopy(query)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                expected_inspections(changed)
        changed = copy.deepcopy(query)
        changed["edges"][0]["src"] = "unknown"
        with self.assertRaises(ValueError):
            expected_inspections(changed)

    def compare_files(self, *, contract=None, mutate=None, unknown=False):
        query = examples()[0]
        old, new, certificate = details(query)
        row = {"id": query["id"], "status": "optimal_bounded", "frontier_candidates": "80",
               "producer_cpu_s": "retained measurement", "peak_rss_kib": "retained RSS"}
        if unknown:
            old = new = {"frontier_exception": "frontier candidate limit"}
            certificate = None
            row["status"] = "unknown"
        with tempfile.TemporaryDirectory() as temporary:
            source, replay = Path(temporary) / "source", Path(temporary) / "replay"
            write_evidence(source, query, old, certificate, row)
            write_evidence(replay, query, new, certificate, row)
            if mutate is not None:
                mutate(source, replay, query)
            return reproduce.compare(source, replay, frontier_inspections=contract)

    def test_controller_contract_is_explicit_and_reports_actual_difference(self):
        with self.assertRaises(ValueError):
            self.compare_files()  # Dense/public/default path has no exception.
        contract = InspectionCompatibility()
        self.assertEqual(1, self.compare_files(contract=contract))
        fields = contract.report_fields()
        self.assertFalse(fields["exact_json_evidence_equal"])
        self.assertFalse(fields["deterministic_count_fields_equal"])
        self.assertTrue(fields["scientific_json_evidence_equal"])
        self.assertEqual(1, fields["frontier_inspection_contract"]["different_counts"])
        equal = InspectionCompatibility()
        query = examples()[-2]
        old, new, _ = details(query)
        equal.compare_details(query, old, new, complete=True)
        self.assertTrue(equal.report_fields()["exact_json_evidence_equal"])
        self.assertEqual(1, self.compare_files(contract=InspectionCompatibility(), unknown=True))

    def test_controller_rejects_changed_query_certificate_csv_or_wrong_counts(self):
        def change_json(source, replay, query, folder, side, change):
            path = (source if side == "retained" else replay) / folder / (query["id"] + ".json")
            value = json.loads(path.read_text())
            change(value)
            path.write_text(json.dumps(value))
        mutations = [
            ("inputs", "current", lambda p: p.update(gas=p["gas"] + 1)),
            ("certificates", "current", lambda c: c["witness"].update(cost=999)),
            ("details", "current", lambda d: d["producer_statistics"].update(candidate_pairs=999)),
            ("details", "retained", lambda d: d["producer_statistics"].update(edge_guard_checks=999)),
            ("details", "current", lambda d: d["producer_statistics"].update(edge_guard_checks=999)),
        ]
        for folder, side, change in mutations:
            with self.subTest(folder=folder, side=side), self.assertRaises(ValueError):
                self.compare_files(contract=InspectionCompatibility(), mutate=lambda s, r, p:
                                   change_json(s, r, p, folder, side, change))
        def csv_change(source, replay, query):
            with (replay / "raw.csv").open(newline="") as stream:
                row = next(csv.DictReader(stream))
            row["frontier_candidates"] = "999"
            with (replay / "raw.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(row))
                writer.writeheader(); writer.writerow(row)
        with self.assertRaises(ValueError):
            self.compare_files(contract=InspectionCompatibility(), mutate=csv_change)


if __name__ == "__main__":
    unittest.main()
