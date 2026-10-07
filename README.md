# Proof-carrying minimal refutations

This repository is the standalone artifact for the finite-summary result in
*Budget-Parametric Proof-Carrying Minimal Refutations for Finite Summary
Systems*. It produces and independently checks exact Pareto-frontier
certificates for bounded first-error paths. It also retains a dense reference
certificate, an interval checker, unpruned forward oracles, search baselines,
complete finite micro-universe validation, adversarial stress cases, public
source provenance cases, mutation tests, and all raw evidence used by the paper.

The artifact is **not** GPS, a C verifier, an SMT-based symbolic executor, an
unbounded optimizer, or a deployment-security tool. Its inputs are benign
finite mathematical control-flow summaries.

## Main result implemented

For every control/data state and remaining-step layer, the frontier certificate
stores the canonical nondominated pairs

```text
(gas consumed, path cost)
```

of first-error paths. Gas charges are binary. The independent checker binds the
certificate to the complete supplied query, verifies the total row domain,
canonical order, exact edge-shifted recurrence, resource caps, and a separately
replayed witness for the least `(cost,gas,initial)` outcome. An accepted
certificate gives the exact least error
cost, or bounded safety, for every gas budget from zero through the declared
cap.

The frontier producer and checker support:

- one 1--6-bit modular register;
- inclusive interval guards;
- modular affine updates or finite havoc;
- nonnegative integer edge costs;
- gas charges in `{0,1}`;
- at most 128 locations, 512 edges, and 128 steps;
- gas caps up to 1,000,000;
- at most 200,000 `(location,value,step-layer)` rows; and
- at most 200,000 shifted frontier candidates per producer/checker run.

A cap or timeout returns `unknown`; it is never converted into an optimality or
safety assertion.

## Retained evidence

The fixed artifact contains:

- **42,372/42,372** complete micro-language agreements among direct
  function-level frontier production/checking, dense production/checking, and
  unpruned forward enumeration (17,210 bounded-optimal, 25,162 bounded-safe);
- **661/661** current frontier/checker and oracle regression results agreeing
  with **661 retained** dense/interval checker records from the earlier study
  (444 optimal, 217 safe); the dense/interval checkers are not rerun in this
  regression phase;
- **14/14** current frontier stress cases, with the independent dense checker
  actually accepting the nine certificates whose dense producer completes and
  five million-gas dense productions returning `unknown`;
- a separate bounded byte-consumer study with **12/12** valid encodings accepted,
  nine duplicate-key/type-binding rejections and three byte-cap unknowns;
- **21/21** function-level malformed-certificate mutations rejected;
- **6/6** exact quotient cases matching retained upstream reachability verdicts;
- **87** passing unit-test methods in the retained study; and
- the legacy 661-case dense/interval study, including three exact unsoundness
  controls and the 82,176-versus-640 inequality boundary measurement.

The five large-gas cases have a largest corresponding dense product of
32,768,032,768 cells. The artifact does not construct that table and makes no
runtime claim about doing so. Four exponential trace families intentionally
exhaust the 200,000-prefix oracle cap and are reported as `unknown` for the
oracle rather than as oracle agreements.

## Environment

Use Linux/Unix and Python 3.10 or later. Only the Python standard library is
required. The full reproduction uses the Unix `resource` module. No package
installation, network access, solver, GPU, model API, private data, paper file,
or external service is needed.

## Clean reproduction

From this repository root, choose a destination that does not yet exist:

```sh
python reproduce.py --out /tmp/pmr-reproduction
```

The controller refuses to overwrite an existing directory. It discovers the
current unit suite and reconstructs the dense phases, frontier regression and stress
phases, public quotients, function-level mutation study, bounded byte-consumer
study, exhaustive micro universe, and both aggregate analyses. It compares every
retained input/certificate JSON object, every scientific detail field and every
deterministic CSV/count field. The one changed frontier producer inspection
diagnostic is validated under the explicit contract below, not equated. CPU time and peak RSS are
reported but intentionally excluded from equality checks.

A successful run writes:

```json
{"status": "semantic_reproduction_passed", ...}
```

This status means that the finite retained study was reproduced. It is not a
mechanized proof of the Python checker, a novelty decision, or peer review.

Run only the tests with:

```sh
python -m unittest discover -s tests -v
```

The finite implementation regression `python -B tests/test_outgoing_index.py`
constructs its own mathematical inputs and independently enumerates first-error
paths for every tested row. It checks input-order-preserving recurrence indexing,
complete certificates and deterministic witnesses, shifted-candidate cap
boundaries, and bounded byte replay with fixed test clocks. This is not a timing
study or a full Unix reproduction. `edge_guard_checks` still counts actual
recurrence inspections, which now exclude other sources' edges; this diagnostic
change is not a reduction of frontier points or scientific candidate work.
Witness extraction and the independent checker are unchanged. Archived result
files remain unchanged. Frontier-phase and public-summary comparison use
`src/frontier_diagnostics.py`: for a completed query it requires the retained
producer count to equal `H * 2**bits * len(nonerror_locations) * len(all_edges)`
and the current producer count to equal
`H * 2**bits * len(edges_with_nonerror_source)`. This covers syntactic error
edges, disabled guards and unreachable locations; layer zero and error rows
inspect nothing. Validation, index construction and witness scans are not in
this recurrence counter. Both counts must be integers and are checked even
when equal. Every other detail field, including checker inspections, shifted
candidates and work caps, remains exact. Incomplete runs retain exact exception
evidence, not a formula for partial work. Public safe/unsafe records require
completed production and a certificate, including bounded-safe null witnesses.
Dense comparison has no diagnostic exception. Wrong counts on either side and
changed scientific fields fail.

`python -B tests/test_frontier_diagnostics.py` checks this contract on owned
finite queries with an independently enumerated inspection-site reference and
negative controls. A successful controller report explicitly records validated
cases and differing counts; `exact_json_evidence_equal` and
`deterministic_count_fields_equal` are false when any inspection count differs,
while scientific-equality flags require all comparisons to complete. This
bounded regression does not establish a new full Unix reproduction or timing.

`python -B tests/test_public_diagnostics.py` additionally exercises the actual
public replay on all six unchanged frozen inputs, independent inspection-site
and first-error-path enumeration, typed scientific-field/count rejection, and
the complete 21-mutation summary. Normal unit discovery includes it. All other
frontier-producer callers were traced: mutations and byte consumers discard its
statistics, and micro/aggregate reports consume unchanged point/candidate fields.
No archived evidence or measurement is updated by these tests.

## Check or produce one frontier certificate

The `tradeoff-8` stress case has a nine-point tight frontier:

```sh
python src/frontier_checker.py \
  results/frontier-stress/inputs/tradeoff-8.json \
  results/frontier-stress/certificates/tradeoff-8.json
```

Produce a fresh certificate outside the retained evidence and check it:

```sh
python src/frontier_producer.py \
  results/frontier-stress/inputs/tradeoff-8.json \
  /tmp/tradeoff-8-certificate.json
python src/frontier_checker.py \
  results/frontier-stress/inputs/tradeoff-8.json \
  /tmp/tradeoff-8-certificate.json
```

Always give the checker the original input separately. A producer file alone is
not a trusted result. The checker returns exit 0 for a fully accepted bounded
result, exit 2 for `unknown`/resource exhaustion, and exit 1 for malformed or
false certificates.

The legacy one-budget dense certificate can be checked with:

```sh
python src/checker.py \
  results/interval-pilot/inputs/gas-erasure.json \
  results/interval-pilot/certificates/gas-erasure.json
python src/interval_checker.py \
  results/interval-pilot/inputs/gas-erasure.json \
  results/interval-pilot/certificates/gas-erasure.json
```

## Repository map

- `src/frontier_producer.py` - exact Pareto-frontier producer.
- `src/frontier_checker.py` - independent exact-recurrence and witness checker;
  imports no producer, model, Pareto, or oracle module.
- `src/frontier_oracle.py` - independently coded unpruned forward semantics.
- `src/frontier_cases.py`, `frontier_study.py`, `frontier_replay.py`,
  `frontier_analyze.py` - fixed regression/stress generation, execution,
  replay, and aggregation.
- `src/tiny_exhaustive.py` - complete enumerator for the declared micro universe.
- `src/mutation_study.py` - 21 targeted function-level certificate/input
  corruptions.
- `src/consumer_boundary_study.py` - independent canonical serialization and
  bounded `check_bytes` replay for all three checkers, including duplicate-key,
  byte-cap, Boolean, and float negatives.
- `src/public_cases.py`, `public_study.py`, `public_replay.py` - six exact finite
  quotients of retained public loop-acceleration sources.
- `src/producer.py`, `checker.py`, `interval_checker.py`, `oracle.py` - legacy
  dense/interval reference path.
- `src/bad_search.py` - deliberately unsound gas/step/value-erasure controls.
- `tests/` - acceptance, rejection, type-binding, deadline, byte-boundary,
  frontier, and representation tests.
- `results/` - exact inputs, certificates, detailed outcomes, CSV files, and
  aggregate JSON used by the paper.
- `public/` - exact retained public C source files, metadata, and upstream
  BSD-style license.
- `proofs/arguments.md` - standalone proof architecture.
- `docs/` - grammar, implementation map, reproduction, resources, literature,
  bibliography audit, and retained reproduction/test reports.
- `claim_evidence_ledger.csv` - material claim-to-proof/test/result map.
- `external_resources.csv` - scholarly, official, template, and public-input
  provenance.

## Scope and trust

The checker is independent of the producer at the module/dependency level and
recomputes the recurrence. The producer and checker are nevertheless Python
programs developed in the same project and reviewed by the same process. The
artifact does not claim an independent-team replication or a machine-checked
implementation theorem.

Bounds are part of every result. Nothing here establishes global optimality for
unbounded executions, arbitrary heaps, concurrency, arbitrary integers, or
source programs. The six public cases use documented exact quotients; they are
not parsed or run as C programs. Existing optimal-planning certificates and
multicriteria shortest-path algorithms are prior work. The scoped contribution
is the finite all-budget certificate/checker interface and its proved binary-gas
size boundary, not the invention of independent optimality certification or
Pareto dynamic programming.


## Retained Linux reproduction

The retained Ubuntu/CPython 3.12.14 clean run passed 98 main tests and replayed
661 dense queries, 675 frontier queries (including fourteen stress systems),
six public quotients, 21 mutations, 24 byte-consumer cases, and the 42,372-query
micro universe. Semantic outputs matched retained results, including the five
dense-producer unknowns and four capped oracles. Child CPU time was 33.598428
seconds and peak child RSS was 35,196 KiB; controller CPU time was 0.858427143
seconds. The supplementary quotient run separately passed 34 tests and the
refinement audit. Raw current records are retained under
`results/measurements/current-linux/`; historical host records are unchanged.
That run used the full-scan producer. It is not a rerun of the indexed producer
or its diagnostic comparison contract.

The bounded scientific workflow runs the Unix controller and supplementary
tests and retains raw outputs on failure as well as success. Timing variation
does not excuse changed scientific fields: summary JSON is compared as a typed
object, while frozen byte-boundary queries and certificates remain byte-exact.

## License

`LICENSE` applies to the newly produced code, generated mathematical inputs,
tests, results, and repository documentation. The retained six public source
files are under the upstream license reproduced in
`public/sv-benchmarks-loop-acceleration/LICENSE`. Scholarly papers and official
web pages are cited but not redistributed. The ACM class/style and their notices
are part of the separate paper package, not this standalone repository.
