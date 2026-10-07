# Reproduction contract

## Prerequisites

- Linux/Unix;
- Python 3.10 or later;
- Python standard library only;
- a fresh writable output path;
- no network, package installation, solver, GPU, model API, private data, or
  manuscript checkout.

The runner uses `resource.setrlimit`, so Windows is not a supported clean-run
environment without replacing that guard.

## Full command

From the standalone repository root:

```sh
python reproduce.py --out /tmp/pmr-reproduction
```

The output path must not exist. The refusal to overwrite avoids mixing old and
new evidence.

## Sequence executed

1. `python -m unittest discover -s tests -v` (discover the current methods;
   the retained historical run had 87).
2. Replay `interval-pilot`, `main`, `family`, and `boundary` dense phases.
3. Compare each dense phase's input, certificate, detail JSON, and every
   deterministic `raw.csv` field.
4. Replay `frontier-regression` and `frontier-stress`.
5. Compare every frontier input, certificate, detail JSON, and deterministic
   CSV field.
6. Replay the six `public-summary-cases` and compare all retained evidence.
7. Regenerate the 21-case function-level mutation study and compare the
   complete summary.
8. Regenerate the separate bounded byte-consumer study: independently
   serialize representative queries/certificates, invoke each checker's
   duplicate-key-rejecting, length-bounded `check_bytes` entry, and compare all
   positive/negative records and bytes.
9. Re-enumerate all 42,372 micro-language queries; compare the semantic/count
   summary after removing CPU/RSS and compare the exact specification and
   stratum table bytes.
10. Regenerate the dense and frontier aggregate reports.
11. Write `reproduction.json`.

Each child receives a 180 s CPU/wall guard and 2.5 GiB address-space guard. The
controller uses one worker. The scientific scripts also enforce their own
product/row/candidate/prefix/file caps.

## Equality definition

Required equality includes:

- input selection and identifiers;
- decoded query JSON;
- decoded certificate JSON;
- decoded detailed result JSON, with the validated frontier diagnostic contract
  below;
- result status, optimum/safety, witness resources, frontier points and widths,
  candidate/work counts, oracle/dense completion flags, mutation outcomes, and
  exhaustive stratum totals; and
- aggregate integer counts.

CPU time and peak RSS are not required to match because they depend on the
machine and process environment. Their measured values remain in the new run's
report.

### Completed frontier inspection compatibility

The two frontier phases and six public-summary cases opt into
`src/frontier_diagnostics.py`: all three drivers call the same indexed frontier
producer. Both public `safe_bounded` and `optimal_bounded` records require
completed production and certificate presence, even when the witness is null.
All inputs,
certificate JSON, CSV fields and scientific detail fields remain exact, including
all checker statistics, producer `candidate_pairs`/`work`, rows, points, peaks,
successor visits, dense/oracle results and retained legacy records. The sole
non-equal detail field is `producer_statistics.edge_guard_checks`; it is not
ignored. Both sides must independently satisfy query-derived formulas:

```text
retained full scan = H * width * number_of_nonerror_locations * number_of_all_edges
current index     = H * width * number_of_edges_with_nonerror_source
width             = 2**bits
```

At each positive layer, every register value at every non-error location is
visited, including unreachable locations. The full scan inspects all syntactic
edges; the index inspects that location's outgoing list, preserving input order.
Disabled guards still require inspections. Error rows and layer zero inspect
nothing; syntactic edges out of errors contribute only to the old all-edge scan.
Gas caps, enabled-successor multiplicity and frontier width do not change these
formulas. Validation, index construction and witness extraction are outside this
recurrence counter. Count types must be integers, not booleans or floats.

Both formulas are checked even if the counts happen to agree. A wrong retained
count, a wrong current count, a missing count, or any changed scientific subtree
fails comparison. Incomplete production has no returned statistics: its exact
exception evidence remains required and no completed-count formula is applied.
Dense phases use exact comparison without this diagnostic contract. Mutation
and byte-consumer drivers discard producer statistics; micro/aggregate drivers
consume unchanged scientific point/candidate fields, not this inspection count.
Their existing summary/byte/count checks remain exact. The
original result files, timing values, functional hashes and byte-consumer
fixtures are not rewritten. Inspection differences are not scientific candidate
reductions or measured speedups.

## Success meaning

If a future complete run succeeds, `reproduction.json` includes these fields
(this schema illustration is not evidence of a new run):

```json
{
  "status": "semantic_reproduction_passed",
  "cases": 661,
  "frontier_cases": 675,
  "public_cases": 6,
  "mutation_cases": 21,
  "exhaustive_micro_cases": 42372,
  "unit_test_suite_passed": true,
  "scientific_json_evidence_equal": true,
  "scientific_count_fields_equal": true,
  "workers": 1
}
```

`frontier_inspection_contract` identifies the field and both scan modes and
records `query_validated_cases` and `different_counts`. The existing
`exact_json_evidence_equal` and `deterministic_count_fields_equal` flags are
derived from whether any validated inspection counts differ; they are **false**
when the counts differ. No claim of whole-JSON/count equality accompanies a
successful scientific comparison under the diagnostic contract. The retained
full-scan Linux run is unchanged; no indexed full Linux run is claimed here.

This establishes reproducibility of the retained finite computations and
artifacts. It does not establish that the Python checker is formally verified,
that the mathematical proofs have been independently audited, that the result
is novel, or that a journal will accept the paper.

## Focused commands

Tests only:

```sh
python -m unittest discover -s tests -v
```

Portable diagnostic contract only (owned finite inputs; no measurements):

```sh
python -B tests/test_frontier_diagnostics.py
```

One frontier certificate:

```sh
python src/frontier_checker.py \
  results/frontier-stress/inputs/tradeoff-8.json \
  results/frontier-stress/certificates/tradeoff-8.json
```

One legacy dense certificate through both checkers:

```sh
python src/checker.py \
  results/interval-pilot/inputs/gas-erasure.json \
  results/interval-pilot/certificates/gas-erasure.json
python src/interval_checker.py \
  results/interval-pilot/inputs/gas-erasure.json \
  results/interval-pilot/certificates/gas-erasure.json
```

Reconcile retained dense results without rerunning solvers:

```sh
python src/analyze.py --results results --out /tmp/pmr-dense-aggregate
```

Reconcile retained frontier results:

```sh
python src/frontier_analyze.py --results results --out /tmp/pmr-frontier-aggregate
```

These analysis-only commands are not substitutes for `reproduce.py`.
