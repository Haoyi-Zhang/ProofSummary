"""Owned finite regressions for the supplementary sandwich certificate."""
import copy
import json
import unittest

from pcrh.checker import CertificateError, check_certificate_object
from pcrh.bounded_checker import check_certificate_bytes_bounded
from pcrh.core import (Edge, System, astar_witness, build_quotient,
                       dense_value_table, make_certificate, ucs_witness)


class ExactArithmeticTests(unittest.TestCase):
    def two_choices(self):
        cost = 2**53 + 3
        model = System(("s", "z"), "s", frozenset({"z"}),
                       (Edge("cheap", "s", "z", 0, cost),
                        Edge("expensive", "s", "z", 0, cost + 1)), 1, 0)
        return model, cost

    def test_exact_integer_lower_table_above_float_boundary(self):
        model, cost = self.two_choices()
        certificate = make_certificate(model, {s: s for s in model.states}, "identity")
        result = check_certificate_bytes_bounded(json.dumps(certificate).encode())
        self.assertEqual({"status": "optimal", "lower": cost, "upper": cost}, result.results[0])

    def test_rounded_up_nonminimum_witness_cannot_be_optimal(self):
        model, cost = self.two_choices()
        certificate = make_certificate(model, {s: s for s in model.states}, "identity")
        certificate["witnesses"]["0"] = {"budget": 0, "cost": cost + 1, "gas": 0,
                                         "steps": 1, "edges": ["expensive"]}
        certificate["claims"]["0"] = {"status": "optimal", "lower": cost + 1, "upper": cost + 1}
        with self.assertRaises(CertificateError):
            check_certificate_bytes_bounded(json.dumps(certificate).encode())

    def test_search_has_no_finite_infinity_sentinel(self):
        cost = 2**62 + 7
        model = System(("s", "z"), "s", frozenset({"z"}), (Edge("e", "s", "z", 0, cost),), 1, 0)
        alpha = {s: s for s in model.states}
        table = dense_value_table(build_quotient(model, alpha))
        self.assertEqual(cost, astar_witness(model, alpha, table, 0)[0]["cost"])
        self.assertEqual(cost, ucs_witness(model, 0)[0]["cost"])

    def test_witness_stops_at_first_error(self):
        model = System(("s", "z"), "s", frozenset({"z"}),
                       (Edge("e", "s", "z", 0, 1), Edge("loop", "z", "z", 0, 0)), 2, 0)
        certificate = make_certificate(model, {s: s for s in model.states}, "identity")
        certificate["witnesses"]["0"]["edges"].append("loop")
        certificate["witnesses"]["0"]["steps"] += 1
        with self.assertRaises(CertificateError):
            check_certificate_object(certificate)

    def test_boolean_claim_does_not_alias_integer(self):
        model = System(("s", "z"), "s", frozenset({"z"}), (Edge("e", "s", "z", 0, 1),), 1, 0)
        certificate = make_certificate(model, {s: s for s in model.states}, "identity")
        for field in ("lower", "upper"):
            bad = copy.deepcopy(certificate)
            bad["claims"]["0"][field] = True
            with self.assertRaises(CertificateError):
                check_certificate_object(bad)


if __name__ == "__main__":
    unittest.main()
