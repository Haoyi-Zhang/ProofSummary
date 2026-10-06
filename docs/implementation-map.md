# Implementation and evidence map

## Frontier certificate path

| Component | Role | Deliberate separation |
|---|---|---|
| `src/frontier_producer.py` | Validates supported input, computes exact layer frontiers, deterministically extracts a witness for the least `(cost,gas,initial)` outcome, writes certificate | Not imported by checker or oracle |
| `src/frontier_checker.py` | Strictly decodes query/certificate, replays witness, reconstructs every exact recurrence row, interprets initial frontier | Imports no project semantics/producer/Pareto/oracle code |
| `src/frontier_oracle.py` | Enumerates bounded forward prefixes without dynamic programming or dominance pruning | Own transition path on well-formed inputs, not a parser; used only as a small exact oracle |
| `src/frontier_cases.py` | Deterministic regression conversion and 14 stress systems | Selection logic separated from checking |
| `src/frontier_study.py` | Runs producer/checker and optional dense/oracle comparisons under caps | Emits exact inputs, certificates, details, and CSV |
| `src/frontier_replay.py` | Re-executes retained frontier inputs without regenerating selection | Used by clean reproduction |
| `src/frontier_analyze.py` | Reconciles regression/stress metrics and generates paper-side rows/CSV when requested | Reads results only; no scientific solver logic |

## Independent validation paths

| Component | Purpose |
|---|---|
| `src/tiny_exhaustive.py` | Enumerates the complete declared 42,372-query micro universe and compares frontier, dense, and forward semantics. |
| `src/mutation_study.py` | Applies 21 targeted function-level corruptions and records the checker's rejection obligation/reason. |
| `src/consumer_boundary_study.py` | Independently serializes representative query/certificate pairs, invokes all three bounded byte consumers, and records 12 positive plus 12 negative results. |
| `src/public_cases.py` | Defines six documented exact finite quotients of retained public C cases. |
| `src/public_study.py`, `src/public_replay.py` | Execute and reproduce the public quotient sanity comparison. |

## Legacy dense and search path

| Component | Role |
|---|---|
| `src/model.py` | Dense producer-only finite semantics and limits. |
| `src/producer.py` | Dense exact suffix distances, clipped certificate, uniform-cost and fixed-guidance witness search. |
| `src/checker.py` | Dense local-inequality and witness checker. |
| `src/interval_checker.py` | Shifted interval-intersection checker for the same dense certificate. |
| `src/oracle.py` | Forward trace enumeration without dynamic programming or pruning. |
| `src/bad_search.py` | Deliberately unsound gas-, step-, and value-erasing searches. |
| `src/cases.py`, `src/run_study.py`, `src/replay_study.py` | Fixed legacy input selection, execution, and replay. |
| `src/analyze.py` | Reconciles the 661 dense cases and generated paper data. |

The dense checker and interval checker share parser/replay design. Their
agreement is useful differential evidence but is not an independent
implementation of the whole semantics. The frontier checker is a separate file
and dependency path, yet all code remains same-project Python.

## Tests and retained results

- `tests/test_frontier.py`: Pareto canonicalization, producer/checker/oracle
  agreement, million-gas handling, strict grammar, mutation-like rejection, and
  stress-family behavior.
- `tests/test_certificate.py`: dense replay and local-obligation acceptance and
  rejection.
- `tests/test_interval.py`, `tests/test_partitions.py`: shifted interval
  equivalence, coverage, merge boundaries, and valid nonmonotone profiles.
- `tests/test_io_bounds.py`: duplicate keys, byte caps, product/row/work limits,
  and status discipline.

The current suite has 93 methods (87 in the retained historical run), including type-sensitive embedded-query
binding, minimum-initial witness ties, duplicate-key rejection, byte-cap limits,
mock-clock deadline checks before zero/sub-128 work returns, and study fail gates
that distinguish rejection, exhaustion, and positive acceptance. `results/` retains
all selected exact inputs
and all claim-linked outputs. `results/pilot` is historical feasibility evidence
and is not double-counted in the 661 regression total.

## Public-source material

`public/sv-benchmarks-loop-acceleration/` contains six exact upstream C files,
selection metadata, an explanatory quotient note, and the upstream license. The
corresponding executable JSON summaries are retained under
`results/public-summary-cases`. No C parser or external verifier is invoked.

## Reproduction controller

`reproduce.py` creates a fresh destination, runs the current 93 tests, replays four
dense phases and two frontier phases, public cases, the 21 function-level
mutations, the separate bounded byte-consumer study, and exhaustive micro
validation, then regenerates both aggregate analyses. It compares exact JSON
objects and all deterministic CSV fields while excluding only CPU and RSS. It
uses one worker and child resource limits. It does not read `paper/`.
