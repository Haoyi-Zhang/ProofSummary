Electronic supplement description

This directory is also the standalone `proof-carrying-minimal-refutations`
repository. It contains the finite summary-language inputs, exact Pareto and
legacy dense certificates, independent checkers, producers, forward oracles,
the current discovered main test suite (87 methods in the retained historical
study), raw results, a separate bounded byte-consumer study, six
licensed public-source provenance cases, mathematical arguments, ledgers, and
the clean reproduction controller.

No manuscript file, network access, package installation, solver, GPU, model
API, private data, or external service is required. Run from this directory:

    python reproduce.py --out /tmp/pmr-reproduction

The destination must not already exist. See `README.md` and
`docs/reproduction.md` for the exact interpretation of a successful run.
