# Resource account and enforced limits

## Intake and campaign envelope

Scientific intake observed a four-core cgroup allowance, a 4 GiB memory limit,
no swap, and sufficient writable storage. No stress test was performed. The
campaign used one worker. No GPU, external compute, model API, package
installation, private data, or live service was used.

Project ceilings were six CPU-hours for the campaign, 2.5 GiB peak RSS per
scientific child, 180 s per component, and archives below 128 MiB. At least one
quarter of the budget was reserved for repair and clean reproduction. Actual
retained runs are orders of magnitude below the CPU and memory ceilings.

## Executable caps

| Family | Limits |
|---|---|
| Frontier producer/checker | bits 1--6; locations <=128; edges <=512; steps <=128; gas <=1,000,000; rows <=200,000; shifted candidates <=200,000; input/certificate <=8 MiB; CPU contract 180 s |
| Dense producer/checkers | same graph/data limits; gas <=128; explicit product cells <=200,000; work/obligations <=200,000; file <=8 MiB; CPU contract 180 s |
| Forward oracle | prefix cap 200,000 and CPU guard; no pruning or dynamic programming |
| Clean controller | one worker; child RLIMIT_CPU 180 s; child address-space limit 2.5 GiB; subprocess wall timeout 180 s |
| Paper build | one process; 45 s per LaTeX/BibTeX command; 2.5 GiB address-space limit; supplied toolchain only |

A cap produces `unknown` or an unsupported-input error. It never silently drops
obligations or turns exhaustion into safety/optimality.

## Retained finite sizes

- Dense regression: 661 cases, 412,682 total product cells, maximum 67,080.
- Dense local comparisons: 461,052; interval comparisons: 31,658.
- Frontier regression: 23,926 retained points and 20,927 shifted candidates.
- Frontier stress: 55,234 retained points and 73,144 shifted candidates.
- Exhaustive micro universe: 274,788 retained points and 94,848 shifted
  candidates over 42,372 queries.
- Largest numerical gas cap: 1,000,000.
- Largest corresponding *theoretical* dense product: 32,768,032,768 cells; that
  product is not allocated or timed.
- Maximum exhaustive-oracle prefixes in the complete micro universe: 30.
- Four stress oracles intentionally reach the 200,000-prefix cap and return
  `unknown`.

## Measurement interpretation

The canonical clean-run report is stored in
`docs/reproduction-report.json`, and the unit-test transcript is stored in
`docs/unit-test-results.txt`. CPU and RSS are environment-dependent and not used
as semantic equality conditions. The paper reports the recorded clean-run
measurements only as a resource account, not as comparative performance.

The 82,176-versus-640 dense/interval inequality count is a deterministic work
count for one boundary instance. It does not imply an end-to-end speedup because
the dense producer still computed 67,080 product cells. Similarly, the
32.8-billion theoretical product demonstrates removal of the numerical gas
factor from the frontier row domain; it is not a measured dense execution.
