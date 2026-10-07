"""Self-contained finite outgoing-index regression; no campaign or timing.

The independent reference enumerates complete first-error paths, then removes
dominated outcomes pairwise. It uses no producer/checker recurrence or historical
implementation. Test clocks are fixed; production CPU guards are not altered.
"""
from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import frontier_producer as fp
import frontier_checker as fc


def edge(identifier, source, destination, gas=0, cost=0, guard=(0, 1), update=(1, 0)):
    return {"id": identifier, "src": source, "dst": destination, "gas": gas,
            "cost": cost, "guard": list(guard),
            "update": update if update == "havoc" else list(update)}


def query(name, locations, edges, gas, steps, bits=1, initial=(0,)):
    return {"id": name, "bits": bits, "locations": locations, "edges": edges,
            "start": locations[0], "errors": [locations[-1]], "initial": list(initial),
            "gas": gas, "steps": steps}


def fixtures():
    result = []
    for dominated in (False, True):
        locations = ["q" + str(i) for i in range(5)]
        edges = [edge(2*i+j, locations[i], locations[i+1], j,
                      j if dominated else 1-j) for i in range(4) for j in (0, 1)]
        result.append(query("index_dominated" if dominated else "index_tradeoff",
                            locations, edges, 4, 4))
    locations = ["q" + str(i) for i in range(9)]
    result.append(query("index_single", locations,
                        [edge(i, locations[i], locations[i+1], 1, i % 5 + 1) for i in range(8)],
                        1000000, 8))
    result.append(query("index_safe_loop", ["s", "z"], [edge(0, "s", "s", 1)], 1000000, 4))
    result.append(query("index_mixed", ["s", "a", "z"],
                        [edge(9, "s", "a", 1, 1, (0, 3), "havoc"),
                         edge(2, "a", "a", 0, 1, (0, 2), (-1, -1)),
                         edge(7, "a", "z", 0, 0, (2, 3), (1, 0)),
                         edge(1, "s", "z", 0, 7, (0, 3), (1, 0))],
                        2, 3, 2, (3, 0)))
    initial_error = query("index_initial_error", ["s", "z"],
                          [edge(8, "s", "z", 0, 4), edge(3, "z", "s", 0, 0)], 0, 3,
                          initial=(1, 0))
    initial_error["errors"] = ["s", "z"]
    result.append(initial_error)
    sparse = query("index_sparse", ["s", "dead", "a", "z"],
                   [edge(41, "dead", "z", 0, 1), edge(12, "a", "z", 0, 0),
                    edge(8, "s", "a", 1, 2, (1, 1)), edge(4, "z", "s", 0, 0),
                    edge(2, "s", "a", 0, 2, (0, 1)), edge(7, "s", "z", 0, 5)],
                   1, 3, initial=(1, 0))
    result.append(sparse)
    for data in list(result):
        reversed_data = copy.deepcopy(data)
        reversed_data["id"] += "_reversed"
        reversed_data["edges"].reverse()
        result.append(reversed_data)
    for bits, gas, steps in itertools.product((1, 2), (0, 1, 3), (0, 1, 3)):
        width = 1 << bits
        result.append(query(f"index_grid_{bits}_{gas}_{steps}", ["s", "a", "z"],
                            [edge(13, "s", "a", 1, 0, (0, width-1), "havoc"),
                             edge(3, "a", "z", 0, 1, (width-1, width-1), (-1, -1)),
                             edge(11, "z", "s", 0, 0, (0, width-1), (1, 0))],
                            gas, steps, bits, (width-1, 0)))
    return result


def reference_successors(data, q, x):
    if q in data["errors"]:
        return []
    width = 1 << data["bits"]
    result = []
    for e in data["edges"]:
        if e["src"] == q and x in range(e["guard"][0], e["guard"][1] + 1):
            for y in range(width):
                update = e["update"]
                if update == "havoc" or (update[0]*x + update[1] - y) % width == 0:
                    result.append((e, y))
    return result


def paths(data, q, x, steps):
    # Enumerate explicit paths. No row recurrence or state dominance is used.
    pending = [(q, x, 0, 0, (), (x,))]
    complete = []
    prefixes = 0
    while pending:
        q, x, gas, cost, derivation, values = pending.pop()
        prefixes += 1
        if prefixes > 5000:
            raise AssertionError("owned reference fixture exceeds its finite prefix bound")
        if q in data["errors"]:
            complete.append((gas, cost, derivation, values))
        elif len(derivation) < steps:
            for e, y in reference_successors(data, q, x):
                if gas + e["gas"] <= data["gas"]:
                    pending.append((e["dst"], y, gas + e["gas"], cost + e["cost"],
                                    derivation + ((e["id"], y),), values + (y,)))
    return complete


def independent_front(data, q, x, steps):
    outcomes = {(gas, cost) for gas, cost, _, _ in paths(data, q, x, steps)}
    return tuple(sorted(pair for pair in outcomes if not any(
        other != pair and other[0] <= pair[0] and other[1] <= pair[1] for other in outcomes)))


def capture(data, max_work=200000):
    with patch.object(fp.time, "process_time", return_value=0):
        try:
            certificate, stats = fp.produce(data, max_work=max_work, seconds=1)
        except fp.Exhausted as exc:
            return {"capped": str(exc)}
        query_bytes = json.dumps(data, separators=(",", ":")).encode()
        cert_bytes = (json.dumps(certificate, separators=(",", ":")) + "\n").encode()
        checked = fc.check(data, certificate, seconds=1)
        self_decoded = fc.check_bytes(query_bytes, cert_bytes, seconds=1)
        assert checked == self_decoded
        return {"certificate": certificate, "serialized_certificate": cert_bytes.decode(),
                "statistics": stats, "checker": checked}


def snapshot():
    """Keep raw changed diagnostics separate, never silently equalize them."""
    records = []
    diagnostics = []
    for data in fixtures():
        complete = capture(data)
        boundary = complete["statistics"]["work"]
        for limit in sorted({0, 1, max(0, boundary-1), boundary, 200000}):
            actual = capture(data, limit)
            if "statistics" in actual:
                inspections = actual["statistics"].pop("edge_guard_checks")
                diagnostics.append([data["id"], limit, inspections])
            records.append([data["id"], limit, actual])
    with patch.object(fp.time, "process_time", side_effect=[0, 2]):
        try:
            fp.produce(fixtures()[0], seconds=1)
        except fp.Exhausted as exc:
            deadline = str(exc)
        else:
            raise AssertionError("CPU guard must fail closed")
    return {"records": records, "edge_inspections": diagnostics, "deadline": deadline}


class OutgoingIndexTests(unittest.TestCase):
    def test_every_row_and_selected_witness_against_complete_paths(self):
        for data in fixtures():
            actual = capture(data)
            expected = {}
            for row in actual["certificate"]["frontiers"]:
                qi, x, h, front = row
                key = (data["locations"][qi], x, h)
                expected[key] = independent_front(data, *key)
                self.assertEqual(tuple(map(tuple, front)), expected[key], (data["id"], key))
            realizations = [(cost, gas, initial, derivation, values)
                            for initial in data["initial"]
                            for gas, cost, derivation, values in paths(
                                data, data["start"], initial, data["steps"])]
            witness = actual["certificate"]["witness"]
            if not realizations:
                self.assertIsNone(witness)
            else:
                cost, gas, initial, derivation, values = min(realizations)
                self.assertEqual(witness, {"initial": initial, "edges": [e for e, _ in derivation],
                                          "values": list(values), "steps": len(derivation),
                                          "gas": gas, "cost": cost})
            # Candidate unit counts every shifted predecessor point BEFORE gas filtering.
            candidates = successors = 0
            for h in range(1, data["steps"]+1):
                for q in data["locations"]:
                    for x in range(1 << data["bits"]):
                        enabled = reference_successors(data, q, x)
                        successors += len(enabled)
                        candidates += sum(len(expected[e["dst"], y, h-1]) for e, y in enabled)
            stats = actual["statistics"]
            indexed_checks = data["steps"] * (1 << data["bits"]) * sum(
                e["src"] not in data["errors"] for e in data["edges"])
            self.assertEqual(stats["edge_guard_checks"], indexed_checks)
            self.assertEqual(stats["candidate_pairs"], candidates)
            self.assertEqual(stats["work"], candidates)
            self.assertEqual(stats["successor_visits"], successors)
            self.assertEqual(capture(data, candidates).get("certificate"), actual["certificate"])
            if candidates:
                self.assertEqual(capture(data, candidates-1), {"capped": "frontier candidate limit"})

    def test_indexed_successor_order_matches_relation_and_default(self):
        for data in fixtures():
            for q in data["locations"]:
                outgoing = [e for e in data["edges"] if e["src"] == q]
                for x in range(1 << data["bits"]):
                    expected = reference_successors(data, q, x)
                    self.assertEqual(list(fp.successors(data, q, x)), expected)
                    self.assertEqual(list(fp.successors(data, q, x, outgoing=outgoing)), expected)

    def test_syntactic_error_edges_still_validate(self):
        data = fixtures()[5]
        data["edges"][1]["cost"] = -1
        with self.assertRaises(fp.Unsupported):
            fp.produce(data)

    def test_deadline_at_indexing_and_before_zero_candidate_return(self):
        data = fixtures()[0]
        with patch.object(fp.time, "process_time", side_effect=[0]*3 + [2]):
            with self.assertRaises(fp.Exhausted):
                fp.produce(data, seconds=1)
        safe = query("index_empty", ["s", "z"], [], 0, 0)
        calls = []
        def counting_clock():
            calls.append(0)
            return 0
        with patch.object(fp.time, "process_time", counting_clock):
            fp.produce(safe, seconds=1)
        with patch.object(fp.time, "process_time", side_effect=[0]*(len(calls)-1) + [2]):
            with self.assertRaises(fp.Exhausted):
                fp.produce(safe, seconds=1)


if __name__ == "__main__":
    unittest.main()
