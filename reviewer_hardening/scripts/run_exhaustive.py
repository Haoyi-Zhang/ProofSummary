#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from pcrh.checker import check_certificate_object
from pcrh.core import Edge, System, build_quotient, dense_value_table, exhaustive_oracle, make_certificate, astar_witness, ucs_witness

STATES = ("p0:0", "p0:1", "p1:0", "p1:1", "err")
BASE_EDGES = (
    Edge("e00", "p0:0", "p0:1", 0, 1),
    Edge("e01", "p0:1", "p0:0", 1, 0),
    Edge("e02", "p0:0", "p1:0", 0, 3),
    Edge("e03", "p0:1", "p1:1", 1, 1),
    Edge("e04", "p1:0", "err", 1, 2),
    Edge("e05", "p1:1", "err", 0, 5),
    Edge("e06", "p1:0", "p1:1", 0, 0),
    Edge("e07", "p1:1", "p1:0", 1, 0),
    Edge("e08", "p0:0", "err", 2, 8),
    Edge("e09", "p0:1", "err", 0, 9),
    Edge("e10", "p1:1", "p0:0", 0, 1),
)
INITIALS = ("p0:0", "p0:1", "p1:0")
GAS_BOUNDS = (0, 1, 2)
HORIZONS = (0, 1, 2, 3)
EDGE_SETS = 1177


def coarse_alpha() -> dict[str, str]:
    return {"p0:0": "p0", "p0:1": "p0", "p1:0": "p1", "p1:1": "p1", "err": "err"}


def middle_alpha() -> dict[str, str]:
    return {"p0:0": "p0:0", "p0:1": "p0:1", "p1:0": "p1", "p1:1": "p1", "err": "err"}


def full_alpha() -> dict[str, str]:
    return {s: s for s in STATES}


def encoded(value: float) -> int | str:
    return "INF" if math.isinf(value) else int(value)


def bootstrap_median_ci(values: list[float], seed: int = 20260920, samples: int = 4000) -> tuple[float, float]:
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    medians = []
    for _ in range(samples):
        medians.append(statistics.median(values[rng.randrange(n)] for _ in range(n)))
    medians.sort()
    return medians[int(0.025 * samples)], medians[min(samples - 1, int(0.975 * samples))]


def main() -> int:
    out_dir = HERE / "results"
    cert_dir = HERE / "certificates"
    out_dir.mkdir(parents=True, exist_ok=True)
    cert_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "exhaustive-queries.csv"
    start = time.perf_counter()
    totals = {
        "queries": 0, "unsafe": 0, "safe": 0,
        "coarse_closed": 0, "middle_closed": 0, "full_closed": 0,
        "needed_refinement": 0, "checker_budget_results": 0,
        "astar_ucs_agreements": 0, "oracle_dp_agreements": 0,
        "monotonicity_checks": 0,
    }
    astar_expansions: list[int] = []
    ucs_expansions: list[int] = []
    reductions: list[float] = []
    sample_gap = None
    sample_refined = None
    fieldnames = [
        "model_index", "mask", "initial", "gas_bound", "horizon", "edge_count",
        "oracle", "coarse_lower", "middle_lower", "full_lower", "closure_level",
        "astar_expansions", "ucs_expansions", "oracle_prefixes",
    ]
    with raw_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for model_index, mask in enumerate(range(EDGE_SETS)):
            edges = tuple(edge for i, edge in enumerate(BASE_EDGES) if mask & (1 << i))
            for initial in INITIALS:
                for gas_bound in GAS_BOUNDS:
                    for horizon in HORIZONS:
                        totals["queries"] += 1
                        concrete = System(STATES, initial, frozenset({"err"}), edges, horizon, gas_bound)
                        oracle_cost, _, prefixes = exhaustive_oracle(concrete, gas_bound)
                        exact_table = dense_value_table(concrete)
                        exact_value = exact_table[horizon][initial][gas_bound]
                        exact_json = encoded(exact_value)
                        if (oracle_cost if oracle_cost is not None else "INF") != exact_json:
                            raise AssertionError((model_index, initial, gas_bound, horizon, oracle_cost, exact_json))
                        totals["oracle_dp_agreements"] += 1
                        if oracle_cost is None:
                            totals["safe"] += 1
                        else:
                            totals["unsafe"] += 1

                        certs = []
                        lowers = []
                        closure = None
                        for level, alpha in (("coarse", coarse_alpha()), ("middle", middle_alpha()), ("full", full_alpha())):
                            cert = make_certificate(concrete, alpha, level)
                            result = check_certificate_object(cert)
                            totals["checker_budget_results"] += len(result.results)
                            query_result = result.results[gas_bound]
                            lower = query_result["lower"]
                            lowers.append(lower)
                            certs.append(cert)
                            if query_result["status"] != "gap" and closure is None:
                                closure = level
                                if level == "coarse":
                                    totals["coarse_closed"] += 1
                                elif level == "middle":
                                    totals["middle_closed"] += 1
                                    totals["needed_refinement"] += 1
                                else:
                                    totals["full_closed"] += 1
                                    totals["needed_refinement"] += 1
                                break
                        if closure is None:
                            raise AssertionError("full partition failed to close")
                        # Complete lower sequence for monotonicity diagnostics even when closed early.
                        while len(lowers) < 3:
                            alpha = (middle_alpha(), full_alpha())[len(lowers)-1]
                            abstract = build_quotient(concrete, alpha)
                            tab = dense_value_table(abstract)
                            lowers.append(encoded(tab[horizon][abstract.initial][gas_bound]))
                        numeric = [math.inf if x == "INF" else int(x) for x in lowers]
                        if not (numeric[0] <= numeric[1] <= numeric[2]):
                            raise AssertionError(("nonmonotone", lowers))
                        if encoded(numeric[2]) != exact_json:
                            raise AssertionError(("full-not-exact", lowers, exact_json))
                        totals["monotonicity_checks"] += 2

                        coarse_abs = build_quotient(concrete, coarse_alpha())
                        coarse_table = dense_value_table(coarse_abs)
                        aw, aexp = astar_witness(concrete, coarse_alpha(), coarse_table, gas_bound)
                        uw, uexp = ucs_witness(concrete, gas_bound)
                        ac = None if aw is None else aw["cost"]
                        uc = None if uw is None else uw["cost"]
                        if ac != oracle_cost or uc != oracle_cost:
                            raise AssertionError(("search disagreement", ac, uc, oracle_cost))
                        totals["astar_ucs_agreements"] += 1
                        astar_expansions.append(aexp)
                        ucs_expansions.append(uexp)
                        if uexp > 0:
                            reductions.append(1.0 - (aexp / uexp))

                        if closure != "coarse" and sample_gap is None:
                            sample_gap = certs[0]
                            sample_refined = certs[-1]
                        writer.writerow({
                            "model_index": model_index, "mask": mask, "initial": initial,
                            "gas_bound": gas_bound, "horizon": horizon, "edge_count": len(edges),
                            "oracle": oracle_cost if oracle_cost is not None else "INF",
                            "coarse_lower": lowers[0], "middle_lower": lowers[1], "full_lower": lowers[2],
                            "closure_level": closure, "astar_expansions": aexp,
                            "ucs_expansions": uexp, "oracle_prefixes": prefixes,
                        })
    assert totals["queries"] == EDGE_SETS * len(INITIALS) * len(GAS_BOUNDS) * len(HORIZONS) == 42372
    if sample_gap is None or sample_refined is None:
        raise AssertionError("enumeration did not exercise a genuine abstraction gap")
    (cert_dir / "coarse-gap.json").write_text(json.dumps(sample_gap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (cert_dir / "refined-closure.json").write_text(json.dumps(sample_refined, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    median_reduction = statistics.median(reductions)
    ci_low, ci_high = bootstrap_median_ci(reductions)
    positive = [max(1e-12, (a + 1) / (u + 1)) for a, u in zip(astar_expansions, ucs_expansions)]
    geometric_ratio = math.exp(sum(math.log(x) for x in positive) / len(positive))
    raw_sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    summary = {
        "schema": "pcrh-exhaustive-summary-v1",
        "enumeration": {
            "edge_sets": EDGE_SETS,
            "initial_states": len(INITIALS),
            "gas_bounds": list(GAS_BOUNDS),
            "horizons": list(HORIZONS),
            **totals,
        },
        "search_ablation": {
            "observations": len(reductions),
            "median_expansion_reduction": median_reduction,
            "bootstrap_95pct_ci_for_median_reduction": [ci_low, ci_high],
            "geometric_mean_smoothed_astar_to_ucs_expansion_ratio": geometric_ratio,
            "primary_metric": "expanded product states; deterministic and machine independent",
            "bootstrap_seed": 20260920,
            "bootstrap_resamples": 4000,
        },
        "raw_csv": {"path": str(raw_path.relative_to(HERE)), "sha256": raw_sha},
        "elapsed_seconds_untrusted": time.perf_counter() - start,
        "interpretation_limits": [
            "The exhaustive language is finite and deliberately small.",
            "Expansion counts support algorithmic comparisons; wall-clock time is not used as the primary claim.",
            "Full-state refinement is a completeness fallback and may forfeit compression.",
        ],
    }
    (out_dir / "exhaustive-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
