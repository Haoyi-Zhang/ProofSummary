# Scholarly provenance, calibration, and novelty boundary

The manuscript bibliography contains 74 entries, all cited. It spans software
model checking, abstraction, summaries, directed/concolic execution,
proof-carrying results, witness validation, shortest paths, multicriteria
optimization, bounded verification, and optimal-search certificates. The exact
key/citation audit is in `bibliography-audit.md`; bibliographic source records
remain in `../paper/references.bib` in the complete project.

## Closest technical boundary

- Fang, Kincaid, and Reps, *Software Model Checking via Summary-Guided Search*,
  DOI 10.1145/3763142, combines formula-valued compositional path summaries,
  directed testing, ART refinement, dead-end interpolation, and gas
  instrumentation for intraprocedural control-state reachability. The current
  artifact does not implement GPS. Its scalar diagnostic cost and exact finite
  Pareto certificate must not be attributed to GPS.
- Mugdan, Christen, and Eriksson, *Optimality Certificates for Classical
  Planning*, ICAPS 2023, DOI 10.1609/icaps.v33i1.27206, already provide
  cost-compilation and direct proof-system routes to planning optimality.
- Dold et al., *Pseudo-Boolean Proof Logging for Optimal Classical Planning*,
  ICAPS 2025, DOI 10.1609/icaps.v35i1.36101, provide lower-bound and search proof
  logging, and the related lower-bound framework has a 2026 Archive of Formal
  Proofs formalization by Traytel.
- Resource-constrained and multicriteria shortest-path work predates the
  project. Canonical Pareto filtering is not claimed as a new algorithm.
- Proof-carrying code, certifying model checkers, and software-verification
  witness validation predate this work. Replaying a trace proves reachability,
  not minimum cost.

The scoped article claim is therefore the exact all-gas certificate interface
for supplied finite summaries, its independent exact-recurrence checker, the
binary-gas tight width boundary, and the retained adversarial validation. It is
not “the first optimality certificate,” “the first Pareto algorithm,” or an
end-to-end GPS extension.

## Writing/evidence calibration

`research-plan.md` records the compact pattern matrix for 13 TOPLAS research
articles, five influential foundations, and five adjacent-venue papers. The
calibration examined complete scholarly records and accessible full-text
introductions, methods/formal sections, evaluation sections, conclusions, and
artifact statements. It was used to calibrate argument sequence, theorem-to-
evidence matching, limitations, and figure/table roles; it was not a claim that
all proofs in those papers were independently reverified or that any work had a
particular award status.

The resulting manuscript sequence is: concrete replay failure; exact semantics;
one-query dense exclusion; interval representation baseline; all-budget
frontier certificate; search/boundedness connection; implementation/trust;
evaluation; related work/limitations/conclusion. Central guarantees stay in the
main paper, with expanded proof, checker, evaluation, diagnostic, and process
appendices.

## Public source provenance

The only external experimental source files embedded in the artifact are six
small files from the public `sv-benchmarks` loop-acceleration directory, with
their upstream BSD-style license. The matching upstream task metadata supplies
three safe and three unsafe unreach-call verdicts. The executable artifact uses
hand-audited exact finite quotients and explicitly does not claim C parsing,
SV-COMP execution, or GPS performance.

Scholarly PDFs, websites, and source repositories are not otherwise copied into
the artifact. URLs, access modes, licenses, and integration roles are listed in
`external_resources.csv`.

## External-use boundary

The current packet is an internal research draft. Direct live TOPLAS and general
ACM submission pages were inaccessible during the final recheck. Before any
submission, human authors must inspect the current first-party rules and verify
template mode, anonymity, supplement upload route, authorship, substantive AI
research disclosure, originality, and any current open-access obligations.
Independent novelty review and independent proof/code audit also remain outside
this artifact's evidence.
