
## Fail-closed resource envelope

The semantic checker is wrapped by `pcrh.bounded_checker`.  Before semantic
checking it enforces explicit limits on input bytes, JSON depth and node count,
collection sizes, strings, and integer magnitude.  Duplicate keys, floats,
NaN/infinity, invalid UTF-8, and truncated JSON are rejected.  Run the retained
negative suite with:

```bash
PYTHONPATH=. python scripts/run_resource_attacks.py --out /tmp/pcrh-resource-attacks
```

The limits are an availability contract, not a semantic assumption: exceeding
a limit returns rejection and never an optimal/safe verdict.

The envelope also bounds the requested abstract table to 200,000 cells and
the recurrence's step/gas/edge visits to 200,000, before allocating that table.
Small JSON scalar dimensions cannot bypass these reconstruction limits.
Finite costs and priorities use exact Python integers, including above
the floating-point exactness boundary. Witnesses stop at the first error.

New certificates include the SHA-256 of the complete concrete model's
canonical JSON (sorted keys, compact separators, ASCII escaping, UTF-8).
The checker validates this annotation when present and always checks a
caller-supplied `expected_model_sha256` against the model itself. Retained
legacy certificates without the annotation remain checkable; self-binding
alone does not validate source-language translation or authenticate a model.

## Repository-wide release gate

From the full project root, a clean end-to-end gate is available as:

```bash
python paper/reviewer-audit/release_gate.py --work-dir /tmp/pcrh-release-gate
```

The work directory must not exist.  The command runs the combined artifact,
rebuilds and audits the paper, checks the PDF and fonts, applies the claim
linter, executes resource attacks, and verifies source-tree hygiene.

## Checkable refinement relation

`pcrh.refinement_checker` does not trust a producer's “refined” label.  It
validates both certificates, derives or checks a factor map from fine abstract
states to coarse abstract states, verifies that the concrete abstraction maps
factor through it, and checks a weighted simulation from the fine abstract
system to the coarse one.  This is the executable premise for monotone lower
bounds.  Run:

```bash
PYTHONPATH=. python scripts/run_refinement_audit.py --out /tmp/pcrh-refinement-audit
```
