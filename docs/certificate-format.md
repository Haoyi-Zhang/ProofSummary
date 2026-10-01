# Input, certificate, status, and trust boundaries

## 1. Query JSON shared by both certificate families

The exact top-level keys are:

```text
id, bits, locations, start, initial, errors, gas, steps, edges
```

Unknown or missing keys are rejected. Duplicate JSON object keys are rejected
by the custom decoder.

- `id`: nonempty descriptive string, at most 80 characters; it is not an
  authentication token.
- `bits`: integer in `1..6`; register values are `0..2**bits-1`.
- `locations`: unique nonempty strings, at most 128.
- `start`: a listed location.
- `initial`: a nonempty duplicate-free list of register values.
- `errors`: a nonempty duplicate-free list of locations.
- `gas`: nonnegative query cap. The frontier family accepts at most 1,000,000;
  the dense family accepts at most 128.
- `steps`: nonnegative cap at most 128.
- `edges`: at most 512 edge objects.

Each edge has exactly:

```text
id, src, dst, guard, update, gas, cost
```

The integer identifier is unique and at most 1,000,000. `guard=[lo,hi]` is an
inclusive register interval. `update=[mul,add]` denotes
`(mul*x+add) mod 2**bits`, with signed 32-bit coefficients; `update="havoc"`
permits every register value. Edge gas is `0` or `1`; cost is an integer in
`0..1,000,000`. Every edge consumes one step. Execution stops at the first
error, even if the input graph has syntactic outgoing error edges. A start state
that is already an error admits the empty witness.

The frontier family requires at most 200,000
`len(locations)*2**bits*(steps+1)` rows. The dense family instead requires at
most 200,000
`len(locations)*2**bits*(gas+1)*(steps+1)` cells.

## 2. Budget-parametric frontier certificate

The exact top-level keys are:

```text
query, witness, frontiers
```

`query` must compare equal to the independently supplied, strictly validated
query. The input file, not the embedded copy or filename, drives semantics.
This is whole-query semantic binding, not cryptographic authentication.

### 2.1 Witness

`witness` is `null` or an object with exactly:

```text
initial, edges, values, steps, gas, cost
```

`values` has one more element than `edges`. The checker replays every edge,
guard, affine/havoc successor, first-error condition, step count, gas sum, and
cost sum. A witness alone proves only reachability and an upper bound.

When the exact initial frontier is nonempty, the frontier checker requires a
witness for the lexicographically least result triple: minimum cost, then
minimum gas, then minimum initial value. This rule fixes the selected outcome,
not the realizing edge sequence. The fixed producer separately uses
deterministic row enumeration, edge/successor tie-breaking, and canonical JSON
serialization; repeated runs of that producer on the same input are byte-stable.
Checker acceptance does not require every valid certificate to use the
producer's row order or the same equal-resource path.

### 2.2 Frontier rows

Every row is:

```text
[location_index, register_value, remaining_steps, [[gas,cost], ...]]
```

Every `(location,value,step)` triple appears exactly once. No gas dimension is
enumerated in the row index. Pairs must have strictly increasing gas and
strictly decreasing cost. Thus they are the canonical componentwise-minimal
outcomes: a pair is omitted exactly when another outcome uses no more gas and
has no greater cost.

For a row `F_h(q,x)`:

- if `q` is an error, the required row is `[(0,0)]` for every `h`;
- if `q` is not an error and `h=0`, the required row is empty;
- otherwise, the checker independently collects every pair obtained by taking
  each enabled edge, every allowed havoc successor, and every pair from the
  successor row at layer `h-1`, then adding edge gas and cost, discarding pairs
  above the query gas cap, and canonicalizing the result.

The supplied row must equal that reconstructed row exactly. The checker performs
at most 200,000 shifted candidate operations. With binary gas, a row at layer
`h` has at most `min(gas_cap,h)+1` pairs; the parser enforces this necessary
bound before recurrence checking.

The exact least cost at any budget `g <= gas_cap` is the minimum `cost` among
initial-frontier pairs whose `gas <= g`. No such pair means bounded safety for
that budget. The command-line checker reports the result at the declared cap
plus the aggregate initial frontier that answers all smaller budgets.

## 3. Legacy dense/interval certificate

The legacy top-level keys are:

```text
query, witness, bounds
```

A row is:

```text
[location_index, register_value, remaining_steps, segments]
```

`segments` partitions every remaining-gas integer in `0..G` with entries
`[lo,hi,bound]`. A bound is a nonnegative integer at most `10**12`, or `null`
for infinity. The dense checker expands every gas cell. The interval checker
shifts a successor interval by the edge gas charge, intersects it with the
source interval and feasible domain, and checks every nonempty constant-value
intersection. It also checks complete feasible-gas coverage.

Both enforce the local lower-bound rule

```text
B(source) <= edge_cost + B(successor)
```

for every enabled primitive successor and sufficient remaining gas. Error bounds
are zero. A matching replayed witness and tight minimum initial lower bound prove
the optimum for the one supplied `(G,H)` query. Infinity at all initial states
proves bounded safety. The interval representation can reduce repeated checks
but has a linear worst case and does not remove the producer's dense product.

## 4. Status and exit-code meaning

| Status | Meaning |
|---|---|
| `optimal_bounded` | Exact bounded optimum and a replayed matching witness. |
| `safe_bounded` | No first-error path exists within the declared gas and step caps. |
| `gap_bounded` | Legacy dense family only: a replayed upper bound and lower bound do not match. This is not optimality. |
| `unknown` | A declared CPU, work, file, row, or product cap was reached. No safety or optimality claim. |
| `rejected` | The input/certificate is malformed or a checked obligation is false. |

Command-line exit codes are 0 for an accepted mathematical result, 2 for
`unknown`, and 1 for rejection or invalid input.

## 5. Trust boundary

The frontier checker imports no producer, model, oracle, search, or Pareto
module. It contains its own strict parser, primitive transition semantics,
canonicalization, recurrence reconstruction, and witness replay. The producer
is untrusted. Retained mutation cases exercise query binding, schema, domain
totality, unique rows, canonical order, recurrence equality, witness grammar,
resource accounting, and first-error replay.

Trusted for an executable run are Python, JSON decoding, the operating system,
the supplied query, and the checker source itself. Successful execution is not a
formal verification of the checker. The producer and checker were developed in
the same project and language, so module independence must not be represented as
independent-team replication.
