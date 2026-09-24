# Bibliography audit

Audit target: `paper/references.bib` and every `.tex` file in the complete
project's `paper/` tree.  The executable audit is
`paper/audit_bibliography.py`; it uses only the Python standard library.

## Deterministic checks

The final clean audit reports:

- BibTeX entries: **74**
- Unique citation keys referenced by TeX: **74**
- Missing citation keys: **0**
- Uncited bibliography entries: **0**
- Duplicate bibliography keys: **0**
- `current.bbl` items after a clean build: **74**
- Undefined references/citations in the final LaTeX log: **0**
- Entries with DOI identifiers: **71**
- Entries with an official HTTPS record but no DOI: **1**
- Books identified by ISBN-13 rather than DOI/URL in BibTeX: **2**
- Entries without a persistent identifier: **0**
- Malformed or duplicate DOI, URL, or ISBN fields: **0**

From the complete project root, after a paper build, run:

```sh
python paper/audit_bibliography.py \
  --bbl /path/to/fresh-paper-build/current.bbl
```

The audit parses balanced BibTeX fields, checks required author/title/year
metadata and identifier syntax/uniqueness, scans every `\\cite...{...}` in the
paper tree, and optionally checks the generated BibTeX item count.  It fails
closed on any mismatch.

## Primary-record checks

The two books use the publisher's ISBN records.  The single URL-only item is the
Archive of Formal Proofs entry for lower-bound planning certificates.  Current
closest-work records for GPS, the 2025 ICAPS optimal-planning certificate and
dynamic-heuristic papers, and the 2026 AFP formalization were checked against
their primary scholarly pages.  The complete resource ledger records the DOI or
official publisher/archive URL used for every bibliography entry.

References are scholarly publications or formal research artifacts needed for
the technical argument.  Venue-rule pages and ordinary websites are workflow
sources in `external_resources.csv`, not manuscript substitutes for scholarly
claims.  Public benchmark provenance is documented in the artifact; the paper
uses the scholarly SV-COMP and witness literature for technical context rather
than inflating the bibliography with web pages.

The deterministic audit establishes key closure, identifier coverage, and
successful typesetting.  It does not prove that no relevant unpublished work
exists, and it cannot substitute for human checking of every quoted technical
claim before external submission.
