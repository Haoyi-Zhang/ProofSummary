from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from frontier_cases import edge, mixed_havoc, program, safe_large_gas, tradeoff_chain
import frontier_checker
from frontier_checker import Limit, Reject, check, check_bytes
from frontier_oracle import enumerate_frontier
import frontier_producer
from frontier_producer import Exhausted, produce


class _CountingClock:
    def __init__(self, expire_on: int | None = None) -> None:
        self.calls = 0
        self.expire_on = expire_on

    def __call__(self) -> float:
        self.calls += 1
        if self.expire_on is not None and self.calls >= self.expire_on:
            return 1.0
        return 0.0


class FrontierCertificateTests(unittest.TestCase):
    def test_tradeoff_frontier_is_exact(self) -> None:
        p = tradeoff_chain(6)
        certificate, stats = produce(p)
        checked = check(p, certificate)
        oracle = enumerate_frontier(p)
        expected = [[g, 6 - g] for g in range(7)]
        self.assertEqual(expected, checked["initial_frontier"])
        self.assertEqual(expected, oracle["frontier"])
        self.assertEqual(7, stats["max_points_per_row"])
        self.assertEqual(0, checked["upper"])
        self.assertEqual(6, checked["witness_gas"])

    def test_safe_large_gas_does_not_expand_gas_dimension(self) -> None:
        p = safe_large_gas()
        certificate, stats = produce(p)
        checked = check(p, certificate)
        self.assertEqual("safe_bounded", checked["status"])
        self.assertIsNone(certificate["witness"])
        self.assertEqual(len(p["locations"]) * 2 * (p["steps"] + 1), stats["rows"])
        self.assertLess(stats["rows"], 1_000)

    def test_mixed_semantics_matches_exhaustive_oracle(self) -> None:
        p = mixed_havoc()
        certificate, _ = produce(p)
        checked = check(p, certificate)
        oracle = enumerate_frontier(p)
        self.assertEqual(oracle["status"], checked["status"])
        self.assertEqual(oracle["cost"], checked["upper"])
        self.assertEqual(oracle["frontier"], checked["initial_frontier"])

    def test_checker_rejects_tampered_frontier(self) -> None:
        p = tradeoff_chain(4)
        certificate, _ = produce(p)
        tampered = copy.deepcopy(certificate)
        for row in tampered["frontiers"]:
            if row[0] == 0 and row[1] == 0 and row[2] == 4:
                row[3] = row[3][:-1]
                break
        with self.assertRaises(Reject):
            check(p, tampered)

    def test_checker_rejects_tampered_witness(self) -> None:
        p = tradeoff_chain(4)
        certificate, _ = produce(p)
        tampered = copy.deepcopy(certificate)
        tampered["witness"]["cost"] += 1
        with self.assertRaises(Reject):
            check(p, tampered)

    def test_explicit_work_limits_return_unknown_not_optimality(self) -> None:
        p = tradeoff_chain(8)
        with self.assertRaises(Exhausted):
            produce(p, max_work=1)
        certificate, _ = produce(p)
        with self.assertRaises(Limit):
            check(p, certificate, max_work=1)


    def test_type_sensitive_query_binding_rejects_bool_bytes(self) -> None:
        p = tradeoff_chain(2)
        certificate, _ = produce(p)
        tampered = copy.deepcopy(certificate)
        tampered["query"]["bits"] = True
        query_bytes = json.dumps(p, separators=(",", ":")).encode()
        cert_bytes = json.dumps(tampered, separators=(",", ":")).encode()
        with self.assertRaises(Reject):
            check_bytes(query_bytes, cert_bytes)

    def test_type_sensitive_query_binding_rejects_equal_float_bytes(self) -> None:
        p = tradeoff_chain(2)
        certificate, _ = produce(p)
        tampered = copy.deepcopy(certificate)
        tampered["query"]["gas"] = float(p["gas"])
        query_bytes = json.dumps(p, separators=(",", ":")).encode()
        cert_bytes = json.dumps(tampered, separators=(",", ":")).encode()
        with self.assertRaises(Reject):
            check_bytes(query_bytes, cert_bytes)

    def test_tied_optimum_requires_least_initial_value(self) -> None:
        p = program(
            "tied-initial", ["s", "z"],
            [edge(0, "s", "z", gas=0, cost=1, guard=[0, 1], update=[1, 0])],
            gas=0, steps=1, bits=1, initial=[0, 1],
        )
        certificate, _ = produce(p)
        accepted = check(p, certificate)
        self.assertEqual(0, accepted["witness_initial"])
        tied_but_noncanonical = copy.deepcopy(certificate)
        tied_but_noncanonical["witness"]["initial"] = 1
        tied_but_noncanonical["witness"]["values"] = [1, 1]
        with self.assertRaises(Reject):
            check(p, tied_but_noncanonical)

    def test_producer_deadline_checked_before_zero_candidate_return(self) -> None:
        p = program("zero-candidate-clock", ["s", "z"], [], gas=0, steps=1)
        counter = _CountingClock()
        with patch.object(frontier_producer.time, "process_time", counter):
            _, stats = produce(p, seconds=0.5)
        self.assertEqual(0, stats["candidate_pairs"])
        expiring = _CountingClock(expire_on=counter.calls)
        with patch.object(frontier_producer.time, "process_time", expiring):
            with self.assertRaises(Exhausted):
                produce(p, seconds=0.5)

    def test_checker_deadline_checked_before_sub128_candidate_return(self) -> None:
        p = tradeoff_chain(2)
        certificate, _ = produce(p)
        baseline = check(p, certificate)
        self.assertLess(baseline["candidate_pairs"], 128)
        counter = _CountingClock()
        with patch.object(frontier_checker.time, "process_time", counter):
            check(p, certificate, seconds=0.5)
        expiring = _CountingClock(expire_on=counter.calls)
        with patch.object(frontier_checker.time, "process_time", expiring):
            with self.assertRaises(Limit):
                check(p, certificate, seconds=0.5)


if __name__ == "__main__":
    unittest.main()
