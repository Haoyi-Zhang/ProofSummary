# Retained public-source sanity cases

These six C files are exact copies of the named files in the public
`sv-benchmarks` loop-acceleration directory as accessed on 2026-09-16.  The
upstream BSD-style license is retained in `LICENSE`.  The expected
`unreach-call` verdicts were read from the matching upstream YAML task files.

The executable study does **not** parse C and is not an SV-COMP run.  Instead,
`src/public_cases.py` defines a hand-audited exact quotient for the assertion
outcome of each selected program:

* `simple_1-*` and `simple_3-*`: `x` starts even and every loop update adds two,
  so parity remains even.  The assertion depends only on parity.
* `simple_2-*`: after the loop, either `x == T` (when the initial value is at
  most `T`) or `x > T` (when it starts above `T`, where
  `T = 0x0fffffff`).  The two-class quotient is exact for the two assertions.

Each quotient has one summary edge with gas and diagnostic cost one, followed
by an assertion-failure edge of cost zero.  The public cases therefore test
source provenance and summary-boundary plumbing only; they do not establish
end-to-end C front-end performance or equivalence to GPS.
