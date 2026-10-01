# Standalone mathematical arguments

This file restates the proof architecture independently of the manuscript. It
uses finite mathematical transition systems and does not claim a mechanized
proof of the Python source.

## 1. Semantics

Let `Q` be a finite set of locations, `X={0,...,2^b-1}` the finite register
domain, `E subset Q` the error locations, and `I subset X` the initial register
values at a distinguished start location `q0`.

An edge `e` has source and destination, an inclusive guard, either a modular
affine update or havoc over all of `X`, a gas charge `d_e in {0,1}`, and a
nonnegative integer cost `c_e`. A primitive transition `(q,x) -e-> (q',x')`
exists when the edge source and guard match and `x'` is the modular affine result
or one of the havoc values. Error locations have no semantic outgoing
transitions: paths stop at the first error.

A bounded query declares a gas cap `G` and step cap `H`. A legal first-error path
starts in `(q0,x0)` for `x0 in I`, reaches an error for the first time after at
most `H` transitions, and consumes at most `G` gas. Its cost is the sum of edge
costs. All sets below are finite.

## 2. Witness replay

A witness explicitly supplies the initial value, edge identifiers, intermediate
register values, step count, gas, and cost. The checker verifies every source,
guard, successor, and first-error condition and recomputes all resources.

**Replay lemma.** If replay accepts a witness, the witness denotes a legal
first-error path of the supplied query, with exactly the reported steps, gas,
and cost.

**Argument.** Induct over the edge list. The base value is a permitted initial
value. At each index, the checker establishes the primitive transition relation
and updates the accumulated resources. It rejects a transition after an error
or a resource excess. Acceptance requires that the final location is an error
and that recomputed and reported totals agree. Therefore the decoded sequence
is exactly a legal path. Replay proves reachability and an upper bound only.

## 3. Exact outcome sets and Pareto normalization

For a base state `u=(q,x)` and step allowance `h`, define

```text
P_h(u) = {(r,c) | there is a first-error path from u
                    with at most h transitions, gas r <= G, and cost c}.
```

For a finite set `S` of resource pairs, let `Pareto(S)` remove every pair
`(r,c)` for which another pair `(r',c')` has `r'<=r`, `c'<=c`, and at least one
strict inequality. For equal gas, only the smallest cost survives. A canonical
frontier is sorted by increasing gas.

**Canonical-frontier lemma.** A canonical frontier has strictly increasing gas
and strictly decreasing cost, is unique, and answers every budget query by

```text
V_S(g) = min{c | (r,c) in Pareto(S), r <= g},
```

with infinity when the set is empty.

**Argument.** Equal-gas minimization is unique. Scan gas values in increasing
order and retain a point exactly when its cost is smaller than every previously
retained cost. A nonretained point is dominated by a retained smaller/equal-gas
point. A retained point cannot be dominated by any smaller-gas point because it
strictly improves the running minimum, nor by a larger-gas point because the
latter uses more gas. Hence the result is exactly the nondominated set and is
unique. Removing dominated points cannot change the minimum cost under any gas
threshold.

## 4. Exact layer recurrence

For every error state `z` and every `h`, the empty path is a first-error path, so

```text
F_h(z) = {(0,0)}.
```

For a nonerror state and `h=0`, no first-error path exists, so the frontier is
empty. For a nonerror state `u` and `h>0`, define the candidate multiset

```text
C_h(u) = union over primitive transitions u -e-> v of
         {(d_e+r, c_e+c) | (r,c) in F_{h-1}(v), d_e+r <= G}.
```

The recurrence sets `F_h(u)=Pareto(C_h(u))`.

**Exact-recurrence theorem.** `F_h(u)=Pareto(P_h(u))` for every state and layer.

**Proof.** Induct on `h` while treating errors by first-error semantics.

- Error state: the only admissible first-error path from an already erroneous
  state is empty, giving `(0,0)`.
- Nonerror state with `h=0`: no transition can be taken and no error is already
  present, so the outcome set is empty.
- Nonerror state with `h>0`: every first-error path has a unique first primitive
  transition `u -e-> v`; its suffix is a first-error path from `v` with at most
  `h-1` steps. Conversely, prefixing any such suffix with the enabled primitive
  transition yields a legal first-error path when the total gas does not exceed
  `G`. Edge resources add. Thus `P_h(u)` is exactly the union of edge-shifted
  `P_{h-1}(v)` sets. By induction, each successor outcome set can be replaced by
  its frontier without changing threshold minima. Pareto reduction of the union
  therefore gives precisely `Pareto(P_h(u))`.

The result quantifies over every concrete havoc successor. Havoc is finite here;
it is not a probabilistic or symbolic shortcut.

## 5. All-budget interpretation

For any budget `g <= G`, let `Opt_h(u,g)` be the minimum cost of a first-error
path from `u` using at most `h` steps and gas at most `g`, with infinity if none
exists.

**All-budget theorem.** For the exact frontier,

```text
Opt_h(u,g) = min{c | (r,c) in F_h(u), r <= g}.
```

**Proof.** By the recurrence theorem, `F_h(u)` is the Pareto reduction of the
complete finite outcome set. The canonical-frontier lemma says Pareto reduction
preserves every gas-threshold minimum. No separate certificate is needed for
different `g` values.

For multiple initial register values, take the union of the corresponding start
frontiers at layer `H` and Pareto-normalize it. The same threshold rule gives the
query optimum for every gas budget. At the declared cap, an empty aggregate
frontier means bounded safety; otherwise its least-cost point is the bounded
optimum.

## 6. Checker-acceptance soundness

The checker validates:

1. strict query and edge grammar plus all numerical caps;
2. exact equality between the independently supplied query and embedded query;
3. one and only one row for every `(location,value,step)` triple;
4. canonical gas/cost order and the binary-gas size precondition;
5. error and zero-step base rows;
6. exact equality with the independently reconstructed edge-shifted recurrence;
7. a separately replayed witness when the aggregate initial frontier is
   nonempty; and
8. equality of witness cost, gas, and initial value with the lexicographically
   least initial outcome.

**Checker theorem.** If the checker accepts `safe_bounded`, no first-error path
exists within the declared step and gas cap. If it accepts `optimal_bounded`,
the replayed witness is a legal first-error path and its cost is the minimum
among all legal paths for the declared cap. The reported aggregate frontier
answers every smaller gas budget exactly.

**Proof.** Totality and exact recurrence make every supplied row the unique exact
frontier by induction on step layers. The all-budget theorem interprets the
aggregate initial frontier. If it is empty, the complete bounded outcome set is
empty. If nonempty, its minimum is a lower and upper semantic value. Replay
provides a legal path at the required resources and cost, so the lower value is
attained. Query binding prevents proving a different instance. Resource
exhaustion is outside the theorem because the implementation returns `unknown`
rather than acceptance.

## 7. Existence and witness extraction

**Existence theorem.** Every supported finite query has a canonical frontier
certificate when implementation caps are ignored.

**Proof.** There are finitely many states, finitely many primitive successors,
and finitely many paths of length at most `H`. Therefore every `P_h(u)` is finite
and has a unique canonical frontier. The exact recurrence constructs all rows
by induction. If the aggregate initial frontier is nonempty, choose its
lexicographically least triple `(cost,gas,initial)`. For a nonerror chosen row,
the recurrence theorem guarantees at least one edge/successor pair whose shifted
successor point derives the chosen point. Repeatedly choose the least edge ID and
successor value among such derivations. The layer decreases at every step, so
extraction terminates at an error with residual `(0,0)`. This gives the
deterministically selected witness used by the fixed producer. The theorem
requires existence of a witness for the least `(cost,gas,initial)` outcome; it
does not make the realizing path unique or force every accepted certificate to
use the producer's row order.

Executable row/candidate/time/file caps qualify only the implementation: a cap
returns `unknown`; it does not refute mathematical existence.

## 8. Dense profile/frontier duality

Let `D_h(u,g)=Opt_h(u,g)` be the exact dense remaining-gas profile. Given a
frontier, recover it by the all-budget threshold minimum. Given a finite dense
profile over `g=0..G`, retain the first finite value and every later gas index at
which the value strictly decreases; store `(g,D_h(u,g))`.

**Duality theorem.** These transformations are inverse up to canonical
representation.

**Argument.** `D_h(u,g)` is nonincreasing in `g` because increasing a budget
cannot remove paths. Each strict decrease records exactly a newly available
nondominated outcome; values between decreases are explained by the last
retained point. Conversely, threshold-minimizing the retained points reconstructs
all dense values. Thus the frontier removes repeated gas-budget values, not
semantic information.

## 9. Binary-gas width and global size

Every path of at most `h` edges consumes an integer gas value in
`0..min(G,h)`. A canonical frontier has at most one point for each gas value.

**Width theorem.** `|F_h(u)| <= min(G,h)+1`.

This bound is tight. Construct a chain of `h` binary choices. At stage `i`, one
edge spends no gas and adds a selected positive cost, while the other spends one
gas and avoids that cost. Choose stage costs so that each additional gas unit
strictly reduces total cost. The terminal error then has one nondominated
outcome for every gas `0..h`, so the width is `h+1` when `G>=h`.

The bound does not imply that every branching system has a wide certificate.
A second family has two choices at each of `h` stages, but one branch is weakly
dominated without changing the reached state. It has `2^h` syntactic paths and
frontier width one.

With `N=|Q|*|X|` base states, the total number of stored points over layers
`0..H` is at most

```text
N * sum_{h=0}^H (min(G,h)+1).
```

For `G>=H`, this is `N*(H+1)*(H+2)/2`, independent of the numerical magnitude of
`G`. Candidate work can still be large because every enabled edge, havoc
successor, and successor-frontier point is visited. The result is not a general
polynomial guarantee in graph size, explicit data domain, or summary language.

**Bounded-integer extension.** If the mathematical language permits edge gas in
`{0,...,B}`, the same argument gives row width at most `min(G,B*h)+1`, and this
is tight. Use an `h`-layer chain with parallel choices `j=0..B`, gas `j`, and
cost `B-j`; every gas total `r=0..B*h` is realizable and has cost `B*h-r`, so
all clipped pairs are nondominated. This shows exactly why the delivered parser
and checker reject nonbinary gas: the implemented `h+1` row cap would otherwise
be unsound. The proposition is a mathematical boundary, not an implemented
extension.

## 10. Dense lower-bound certificates

For the legacy one-query representation, a table `B(q,x,g,h)` has error value
zero and satisfies, for every enabled primitive transition of gas `d` and cost
`c` with `g>=d`,

```text
B(q,x,g,h) <= c + B(q',x',g-d,h-1).
```

**Lower-bound theorem.** `B` lower-bounds every legal first-error continuation.

**Proof.** Apply the local inequality along a path and telescope. The terminal
error value is zero, so the starting bound is at most the path cost. Taking the
minimum over initial states yields a lower bound on the bounded optimum. A
replayed witness of the same cost proves optimality; infinity at all initial
cells proves bounded safety.

Exact suffix distances satisfy the recurrence and give a complete finite
certificate. Clipping a locally valid bound at an upper bound preserves every
local inequality because `min(U,a) <= min(U,c+b)` follows from `a<=c+b` and
`c>=0`. Arbitrary semantic lower bounds need not satisfy local closure and can
correctly be rejected.

## 11. Shifted gas-interval equivalence

Suppose a dense row is encoded as constant closed intervals. For an edge of gas
`d`, a source interval `I` and successor interval `J` apply together to source
budgets in

```text
K = I intersect (J+d) intersect [d,G].
```

The source partition and shifted successor partition make the nonempty `K`
sets a partition of every feasible gas integer. Both table values and edge cost
are constant on each `K`, so checking one inequality per nonempty intersection
is equivalent to expanding all dense gas cells. A two-pointer merge advances at
least one interval index each iteration and checks every intersection in at
most `k+m-1` iterations for row lengths `k,m`.

The representation has a linear worst case: a profile that changes at every gas
value requires `G+1` singleton intervals. Interval checking reduces repeated
comparisons only when profiles are compact; it does not eliminate dense
production.

## 12. Search guidance and replacement

Forget guards and register updates but retain control, costs, gas, and steps.
The exact relaxed suffix optimum is at most every concrete suffix cost, so it is
admissible. Each concrete transition has a corresponding relaxed transition,
which gives consistency. Uniform-cost/A* search on the full concrete product is
therefore optimal when uncapped; the guide changes scheduling, not certificate
acceptance.

A conventional sufficient prefix replacement rule at the same concrete
`(q,x)` is: prefix 1 has no greater cost, no less remaining gas, and no fewer
remaining steps than prefix 2. Every continuation of prefix 2 can be replayed
from prefix 1, preserving suffix transitions and cost. Omitting gas, steps, or
register value without another simulation theorem is unsound; the retained
controls each report cost 9 while a cost-1 error exists.

## 13. Bounded versus global

Increasing `G` or `H` can only add paths, so the optimum is nonincreasing. A
bounded optimum need not be globally optimal. In an unbounded machine-simulating
language, combine an immediate cost-1 error with a cost-0 branch that reaches an
error exactly when the simulated machine halts. A terminating global minimizer
would distinguish optimum zero from one and decide halting. This is a standard
scope boundary, not a new undecidability result for the implemented finite
fragment.

A conditional lift is possible. Suppose integer potentials and nonnegative
constants satisfy, on every edge relevant to a first error,

```text
1 <= a*c_e + psi(v)-psi(v')
d_e <= b*c_e + phi(v)-phi(v')
```

and all permitted initial/error pairs have bounded potential differences
`Delta_psi, Delta_phi`. Any cost-`C` error then has length at most
`a*C+Delta_psi` and gas at most `b*C+Delta_phi` by telescoping. If a bounded
optimum `U>0` is certified with

```text
H >= a*(U-1)+Delta_psi
G >= b*(U-1)+Delta_phi,
```

then every globally cheaper error would fit inside the bounded query, a
contradiction. For `U=0`, nonnegative costs already imply global minimality. No
potential producer or checker is implemented, so this theorem is not used to
upgrade artifact results.
