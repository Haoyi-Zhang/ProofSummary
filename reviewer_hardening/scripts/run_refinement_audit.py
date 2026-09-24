from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pcrh.checker import CertificateError  # noqa: E402
from pcrh.refinement_checker import (  # noqa: E402
    check_refinement_relation,
    derive_refinement_map,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    coarse = json.loads((ROOT / "certificates" / "coarse-gap.json").read_text())
    fine = json.loads((ROOT / "certificates" / "refined-closure.json").read_text())
    rho = derive_refinement_map(coarse, fine)
    valid = check_refinement_relation(coarse, fine, rho=rho)

    attacks: dict[str, bool] = {}
    if len(set(rho.values())) > 1:
        bad = dict(rho)
        key = sorted(bad)[0]
        bad[key] = next(v for v in sorted(set(bad.values())) if v != bad[key])
        try:
            check_refinement_relation(coarse, fine, rho=bad)
        except CertificateError:
            attacks["wrong_factor_target"] = True
        else:
            attacks["wrong_factor_target"] = False
    else:
        # A domain omission is always invalid and does not depend on target count.
        bad = dict(rho); bad.pop(sorted(bad)[0])
        try:
            check_refinement_relation(coarse, fine, rho=bad)
        except CertificateError:
            attacks["missing_factor_domain"] = True
        else:
            attacks["missing_factor_domain"] = False

    result = {
        "schema": "pcrh-refinement-audit-v1",
        "status": "refinement_audit_passed" if all(attacks.values()) else "failed",
        "valid_relation": asdict(valid),
        "factor_map": rho,
        "negative_checks": attacks,
    }
    (args.out / "refinement-audit-summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "refinement_audit_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
