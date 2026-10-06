from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from pcrh.checker import CertificateError
from pcrh.refinement_checker import check_refinement_relation, derive_refinement_map


ROOT = Path(__file__).resolve().parents[1]


class RefinementCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.coarse = json.loads((ROOT / "certificates" / "coarse-gap.json").read_text())
        cls.fine = json.loads((ROOT / "certificates" / "refined-closure.json").read_text())

    def test_committed_pair(self) -> None:
        rho = derive_refinement_map(self.coarse, self.fine)
        result = check_refinement_relation(self.coarse, self.fine, rho=rho)
        self.assertTrue(result.accepted)

    def test_wrong_factor_target(self) -> None:
        rho = derive_refinement_map(self.coarse, self.fine)
        key = sorted(rho)[0]
        targets = sorted(set(rho.values()))
        alternate = next((x for x in targets if x != rho[key]), None)
        if alternate is None:
            self.skipTest("sample coarse abstraction has one state")
        rho[key] = alternate
        with self.assertRaises(CertificateError):
            check_refinement_relation(self.coarse, self.fine, rho=rho)

    def test_different_resource_bound(self) -> None:
        bad = copy.deepcopy(self.fine)
        # Any semantic tamper is rejected before relation checking.
        bad["concrete"]["horizon"] += 1
        with self.assertRaises(CertificateError):
            check_refinement_relation(self.coarse, bad)


if __name__ == "__main__":
    unittest.main()
