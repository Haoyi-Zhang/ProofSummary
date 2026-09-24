#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from pcrh.checker import CertificateError, check_certificate_bytes, check_certificate_object
from pcrh.core import Edge, System, make_certificate

STATES = ("p0:0", "p0:1", "p1:0", "p1:1", "err")
EDGES = (
    Edge("a", "p0:0", "p0:1", 0, 1),
    Edge("b", "p0:1", "p1:1", 1, 1),
    Edge("c", "p1:0", "err", 1, 2),
    Edge("d", "p1:1", "err", 0, 5),
    Edge("e", "p0:0", "p1:0", 0, 3),
)
ALPHA = {"p0:0": "p0", "p0:1": "p0", "p1:0": "p1", "p1:1": "p1", "err": "err"}


def rejected(name: str, mutator, cert: dict) -> tuple[str, str]:
    obj = copy.deepcopy(cert)
    mutator(obj)
    try:
        check_certificate_object(obj)
    except CertificateError as exc:
        return name, str(exc)
    raise AssertionError(f"mutation unexpectedly accepted: {name}")


def main() -> int:
    model = System(STATES, "p0:0", frozenset({"err"}), EDGES, 3, 2)
    cert = make_certificate(model, ALPHA, "mutation-base")
    base = check_certificate_object(cert)
    if not base.valid:
        raise AssertionError("base certificate invalid")
    witness_budget = next(int(k) for k, v in cert["witnesses"].items() if v["edges"])
    mutations = []
    mutations.append(("unsupported-schema", lambda c: c.__setitem__("schema", "v0")))
    mutations.append(("malformed-model-digest", lambda c: c["model_binding"].__setitem__("canonical_sha256", "xyz")))
    mutations.append(("mismatched-model-digest", lambda c: c["model_binding"].__setitem__("canonical_sha256", "0" * 64)))
    mutations.append(("extra-top-level-key", lambda c: c.__setitem__("surprise", 1)))
    mutations.append(("missing-top-level-key", lambda c: c.pop("claims")))
    mutations.append(("duplicate-concrete-state", lambda c: c["concrete"]["states"].append(c["concrete"]["states"][0])))
    mutations.append(("invalid-concrete-initial", lambda c: c["concrete"].__setitem__("initial", "ghost")))
    mutations.append(("invalid-concrete-error", lambda c: c["concrete"]["errors"].append("ghost")))
    mutations.append(("duplicate-concrete-error", lambda c: c["concrete"]["errors"].append("err")))
    mutations.append(("duplicate-edge-id", lambda c: c["concrete"]["edges"][1].__setitem__("id", c["concrete"]["edges"][0]["id"])))
    mutations.append(("invalid-edge-source", lambda c: c["concrete"]["edges"][0].__setitem__("src", "ghost")))
    mutations.append(("boolean-edge-gas", lambda c: c["concrete"]["edges"][0].__setitem__("gas", True)))
    mutations.append(("negative-edge-cost", lambda c: c["concrete"]["edges"][0].__setitem__("cost", -1)))
    mutations.append(("boolean-horizon", lambda c: c["concrete"].__setitem__("horizon", False)))
    mutations.append(("resource-bound-mismatch", lambda c: c["abstraction"]["system"].__setitem__("gas_bound", c["abstraction"]["system"]["gas_bound"] + 1)))
    mutations.append(("alpha-missing-state", lambda c: c["abstraction"]["alpha"].pop("p0:0")))
    mutations.append(("alpha-outside-domain", lambda c: c["abstraction"]["alpha"].__setitem__("p0:0", "ghost")))
    mutations.append(("alpha-not-surjective", lambda c: c["abstraction"]["system"]["states"].append("ghost")))
    mutations.append(("abstract-initial-mismatch", lambda c: c["abstraction"]["system"].__setitem__("initial", "p1")))
    mutations.append(("abstract-error-coverage", lambda c: c["abstraction"]["system"].__setitem__("errors", [])))
    mutations.append(("remove-all-abstract-edges", lambda c: c["abstraction"]["system"].__setitem__("edges", [])))
    mutations.append(("break-weighted-coverage", lambda c: [e.__setitem__("gas", e["gas"] + 10) for e in c["abstraction"]["system"]["edges"]]))
    mutations.append(("lower-layer-count", lambda c: c["lower_table"].pop()))
    mutations.append(("lower-state-key", lambda c: c["lower_table"][0].pop(next(iter(c["lower_table"][0])))))
    mutations.append(("lower-row-width", lambda c: c["lower_table"][0][next(iter(c["lower_table"][0]))].pop()))
    mutations.append(("lower-recurrence-value", lambda c: c["lower_table"][-1][c["abstraction"]["system"]["initial"]].__setitem__(-1, 999999)))
    mutations.append(("lower-boolean-value", lambda c: c["lower_table"][0][next(iter(c["lower_table"][0]))].__setitem__(0, True)))
    mutations.append(("unknown-witness-edge", lambda c: c["witnesses"][str(witness_budget)]["edges"].__setitem__(0, "ghost")))
    mutations.append(("witness-cost-mismatch", lambda c: c["witnesses"][str(witness_budget)].__setitem__("cost", c["witnesses"][str(witness_budget)]["cost"] + 1)))
    mutations.append(("witness-gas-mismatch", lambda c: c["witnesses"][str(witness_budget)].__setitem__("gas", c["witnesses"][str(witness_budget)]["gas"] + 1)))
    mutations.append(("witness-step-mismatch", lambda c: c["witnesses"][str(witness_budget)].__setitem__("steps", c["witnesses"][str(witness_budget)]["steps"] + 1)))
    mutations.append(("witness-budget-mismatch", lambda c: c["witnesses"][str(witness_budget)].__setitem__("budget", witness_budget + 1)))
    mutations.append(("witness-truncation", lambda c: c["witnesses"][str(witness_budget)]["edges"].pop()))
    mutations.append(("claim-status", lambda c: c["claims"]["0"].__setitem__("status", "optimal" if c["claims"]["0"]["status"] != "optimal" else "gap")))
    mutations.append(("claim-lower", lambda c: c["claims"]["0"].__setitem__("lower", 123456)))
    mutations.append(("claim-upper", lambda c: c["claims"]["0"].__setitem__("upper", 123456)))
    mutations.append(("missing-budget-claim", lambda c: c["claims"].pop("0")))
    mutations.append(("extra-budget-claim", lambda c: c["claims"].__setitem__("99", {"status":"gap","lower":0,"upper":"INF"})))
    mutations.append(("extra-budget-witness", lambda c: c["witnesses"].__setitem__("99", copy.deepcopy(next(iter(c["witnesses"].values()))))))
    results = [rejected(name, fn, cert) for name, fn in mutations]

    # Parser-level attacks, including duplicate keys and non-standard constants.
    parser_attacks = {
        "duplicate-json-key": b'{"schema":"x","schema":"y"}',
        "nan-json": b'{"schema": NaN}',
        "invalid-utf8": b'\xff\xfe',
        "truncated-json": b'{"schema":',
    }
    for name, payload in parser_attacks.items():
        try:
            check_certificate_bytes(payload)
        except CertificateError as exc:
            results.append((name, str(exc)))
        else:
            raise AssertionError(f"parser attack accepted: {name}")

    # A sound but imprecise abstraction must be accepted only as a gap, never as exact.
    gap_budgets = [b for b, r in base.results.items() if r["status"] == "gap"]
    if not gap_budgets:
        raise AssertionError("base fixture did not exercise gap semantics")
    downgrade = {"accepted": True, "gap_budgets": gap_budgets,
                 "meaning": "sound lower bound accepted; exactness withheld until a matching witness closes the gap"}
    summary = {
        "schema": "pcrh-mutation-summary-v1",
        "base_valid": True,
        "hard_rejections": len(results),
        "mutations": [{"name": name, "diagnostic": diagnostic} for name, diagnostic in results],
        "safe_downgrade": downgrade,
        "status": "pass",
    }
    path = HERE / "results" / "mutation-summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"hard_rejections": len(results), "safe_downgrade_budgets": len(gap_budgets), "status": "pass"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
