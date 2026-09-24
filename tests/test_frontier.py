from __future__ import annotations

import copy
import unittest

from frontier_cases import mixed_havoc, safe_large_gas, tradeoff_chain
from frontier_checker import Limit, Reject, check
from frontier_oracle import enumerate_frontier
from frontier_producer import Exhausted, produce


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


if __name__ == "__main__":
    unittest.main()
