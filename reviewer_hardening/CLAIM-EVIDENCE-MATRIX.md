
## Additional release-hardening claims

| Claim | Formal/code locus | Positive evidence | Negative evidence |
|---|---|---|---|
| The release checker fails closed before semantic work on over-limit or non-strict JSON. | `pcrh/bounded_checker.py` | valid committed refined certificate | `tests/test_resource_envelope.py`; `results/resource-attack-summary.json` |
| New annotated certificates validate the exact serialized concrete model; an externally expected digest binds the consumer to its intended model. | model-digest check in `pcrh/checker.py` | current generated certificates and expected-digest API tests | model-substitution and malformed-digest mutations |
| No source-language correctness is inferred from self-binding alone. | paper model-binding subsection; `THREATS-TO-VALIDITY.md` | caller-supplied expected digest API | public-source bridge explicitly leaves frontend correctness external |
| The bounded checker has no dependency on producer/search code. | `tests/test_bounded_checker_independence.py` | static import audit and checker-only run | test fails on any `core`, producer, or search import |
| A reported refinement is a checked semantic relation, not a label. | `pcrh/refinement_checker.py` | committed coarse/fine certificate pair | wrong/partial factor-map negative checks |

Retained legacy certificates without a digest annotation remain checkable.
Without a caller-supplied expected digest, neither their acceptance nor a new
certificate's self-binding authenticates the consumer's intended source model.
