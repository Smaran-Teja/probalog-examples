# Probalog examples and benchmarks

Example programs for `#lang roulette/example/probalog`, a probabilistic
Datalog built on [Roulette](https://github.com/Smaran-Teja/roulette),
together with benchmarks comparing it against ProbLog, cplint/PITA and
Soufflé.

Install the language first, from the root of a roulette checkout:

```
raco pkg install --auto roulette/ roulette-lib/
```

Then run any example:

```
racket basics/network-example.rkt
```

Every query in these files carries the answer it should produce, worked
out by hand where that is feasible. A comment that stops matching the
output is a regression signal.

Or all of them:

```
for f in */*.rkt; do echo "== $f"; racket "$f"; done
```

These are examples, not tests. The correctness suite — expected query
probabilities, every read error, every run-time error — lives with the
implementation, at `roulette/roulette/test/probalog.rkt`, and runs with
`raco test roulette/test/probalog.rkt`.

## `basics/`

| file                                                     | what it shows                                                                                       |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| [network-example.rkt](basics/network-example.rkt)        | the smallest complete program: probabilistic facts, a recursive rule, queries                       |
| [family-example.rkt](basics/family-example.rkt)          | the classic family-relations program, with one uncertain parentage record                           |
| [edge-cases.rkt](basics/edge-cases.rkt)                  | a reference for the whole surface syntax: nullary predicates, numeric constants, layout, projection |

## `models/`

Realistic models, each ending in a set of observations and posteriors.

| file                                       | what it shows                                                                                    |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| [alarm.rkt](models/alarm.rkt)              | Pearl's burglary/earthquake network: nullary predicates, CPTs as noisy-or, **explaining away**    |
| [smokers.rkt](models/smokers.rkt)          | "friends and smokers": recursion around a cyclic relation, and how to write a probabilistic rule |
| [observation.rkt](models/observation.rkt)  | intrusion detection with unreliable sensors: false positives and false negatives in one model    |

## `semantics/`

What the language computes, in cases where the answer is easy to get
wrong.

| file                                          | what it shows                                                                                       |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| [correlation.rkt](semantics/correlation.rkt)  | the disjoint-sum problem: seven programs with hand-computable answers, next to what assuming independence would give |
| [cycles.rkt](semantics/cycles.rkt)            | recursion in every shape: cyclic graphs, self-loops, mutual recursion, non-linear recursion         |

## `ported/`

Standard examples from Soufflé and ProbLog, brought over unchanged
where the language allows it. Each file notes what had to be adapted:
probalog puts probabilities on facts rather than rules, and has no
negation, no disequality and no annotated disjunctions.

| file                                                            | ported from                                                            | what it shows                                                                          |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| [souffle-points-to.rkt](ported/souffle-points-to.rkt)           | Soufflé's tutorial (Andersen's analysis, the core of Doop)             | probabilistic program analysis: unresolved reflection and virtual dispatch as confidences, and why two candidates are *not* an exclusive choice here |
| [souffle-same-generation.rkt](ported/souffle-same-generation.rkt) | the classic `sg` benchmark, in Soufflé's test suite                    | the recursive atom in the middle of the body — bindings flowing in from `up` and out through `down` |
| [problog-biomine.rkt](ported/problog-biomine.rkt)               | ProbLog's flagship Biomine application                                 | connection probability in a biological network: exact 0.4153 against 0.5569 from treating paths as independent |
| [problog-genetics.rkt](ported/problog-genetics.rkt)             | ProbLog's genetics/bloodtype examples                                  | a pedigree where `:: 0.5` *is* meiosis; recovers the textbook 1/4 recurrence risk and 2/3 carrier probability |
| [problog-epidemic.rkt](ported/problog-epidemic.rkt)             | ProbLog's epidemic / viral-marketing examples                          | unrolling time without arithmetic, contact tracing backwards from a positive test        |

Two ProbLog staples are deliberately absent. The sprinkler/grass
network is the same noisy-or shape as [alarm.rkt](models/alarm.rkt),
which already covers it. A hidden Markov model is not expressible at
all: mutually exclusive states need negation or annotated
disjunctions, so [problog-epidemic.rkt](ported/problog-epidemic.rkt)
uses a monotone process instead, and says why.

## `bench/`

| file                                                     | what it shows                                                                              |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| [compare-problog.sh](bench/compare-problog.sh)           | sets up ProbLog in a local virtualenv and runs the comparison — the entry point            |
| [compare-problog.py](bench/compare-problog.py)           | probalog against ProbLog on matched programs: wall time, and whether they agree            |
| [compare-cplint.sh](bench/compare-cplint.sh)             | the same against cplint/PITA — the entry point                                             |
| [compare-cplint.py](bench/compare-cplint.py)             | probalog against PITA                                                                      |
| [compare-souffle.sh](bench/compare-souffle.sh)           | the same against Soufflé — the entry point                                                 |
| [compare-souffle.py](bench/compare-souffle.py)           | probalog against Soufflé, run with and without probability annotations                     |
| [probalog-examples.rkt](bench/probalog-examples.rkt)     | four generated program families with per-phase timing instrumentation                      |
| [probalog-plot.rkt](bench/probalog-plot.rkt)             | a stacked-bar plot of that timing                                                          |

`compare-cplint.py` imports its program generators from
`compare-problog.py`, so those two run byte-identical models.
`compare-souffle.py` has its own, because Soufflé needs type
declarations and an output relation rather than a query — the program
shapes match but the code is separate.

`probalog-plot.rkt` opens a plot window, and requiring it runs the
benchmarks first.

### Against ProbLog

`compare-problog.py` generates the same model in both syntaxes, runs
both systems, and checks the answers against each other and against a
Monte Carlo simulation. ProbLog is a Python package, so the wrapper
script installs it into `bench/.venv` and runs the comparison:

```
./bench/compare-problog.sh --quick
```

The virtualenv is built once and reused, so only the first run pays
the install (about 13 seconds). Arguments pass straight through:

```
./bench/compare-problog.sh                            # every suite
./bench/compare-problog.sh dag smokers --timeout 30   # named suites
./bench/compare-problog.sh chordring --verify         # add Monte Carlo
./bench/compare-problog.sh --all-queries              # equal-work mode
./bench/compare-problog.sh --rebuild                  # reinstall
```

`--all-queries` matters for reading the numbers honestly. ProbLog and
PITA are goal-directed: they ground only what the query needs.
probalog computes the entire relation whatever you ask it. So the
default single-query mode charges probalog for work its opponents
never do, and `--all-queries` asks both for the whole relation
instead. On a 20-node ring:

|                | 1 query | all 400 tuples |
| -------------- | ------: | -------------: |
| probalog       |   0.70s |          0.84s |
| ProbLog (sdd)  |   0.12s |          0.17s |

probalog barely notices the extra 399 queries, because it had already
computed the whole relation and a marginal is a weighted count over a
diagram that already exists. ProbLog grows with the number of goals.
The gap closes slowly at these sizes; it is the trend that differs,
not yet the totals.

**Correctness.** probalog agreed with ProbLog on every program tested,
and disagreed only where ProbLog was wrong: ProbLog's *default*
knowledge compiler is dsharp, and on the 16-node chorded ring it
reports `13659.889` as a probability. probalog gives 0.938658,
ProbLog's SDD backend gives 0.9386584, and a 2M-trial Monte Carlo
gives 0.9388. Hence the `pysdd` install and the `-k sdd` this script
passes; `--backend ddnnf` reproduces the bad answer.

**Timings**, single query, 10s timeout:

| workload           | ProbLog (sdd) | probalog |
| ------------------ | ------------: | -------: |
| layered DAG (6,5)  |         1.45s |    1.07s |
| layered DAG (7,5)  |       timeout |    1.70s |
| layered DAG (6,6)  |       timeout |    4.64s |
| chorded ring n=16  |         0.12s |    1.06s |
| smokers ring n=13  |         0.09s |    0.87s |
| smokers ring n=14  |         0.08s |    0.79s |
| smokers ring n=15  |         0.07s |    0.82s |

probalog wins on the layered DAGs and loses everywhere else. ProbLog
times out from DAG (7,5) upward, where probalog is still under two
seconds.

Everywhere else probalog is flat but offset. The smokers ring does not
grow with n at all — 0.84 / 0.95 / 0.87 / 0.79 / 0.82s for n=10 through
15 — and roughly 0.3s of each of those is Racket starting up, so what
is left is a constant few hundred milliseconds against ProbLog's
constant 0.08s. Compiling guards as the derivation proceeds is what
makes those curves flat; the residual gap is a constant factor, not a
growth rate.

### Against cplint/PITA

```
./bench/compare-cplint.sh --quick
```

The wrapper installs SWI-Prolog's `cplint` pack on first run. Note
that cplint is Prolog rather than Datalog; every program here is in
the function-free fragment, so it does not bias the result, but PITA
is solving a more general problem than it needs to. PITA is also
goal-directed, so `--all-queries` applies here too.

**PITA agreed with probalog on all 19 configurations.** With ProbLog,
Soufflé and Monte Carlo, that is four independent confirmations.

| workload           |    PITA | probalog |
| ------------------ | ------: | -------: |
| ring (20)          |   0.17s |    0.79s |
| chorded ring (16)  |   0.19s |    1.07s |
| layered DAG (6,5)  | timeout |    1.27s |
| layered DAG (6,6)  | timeout |    4.23s |
| smokers ring (15)  |   0.22s |    0.80s |

PITA times out on the same DAGs ProbLog struggled with, from (6,5)
upward. On the smokers ring it is flat at ~0.20s across every size, as
is probalog at 0.80–0.89s. PITA is the closest comparison here: it
uses the same strategy of carrying a compiled representation through
the derivation rather than compiling an accumulated formula at the
end, which is why both curves are flat.

### Against Soufflé

```
brew install souffle
./bench/compare-souffle.sh --quick
```

Soufflé is pure Datalog with no notion of probability, so this runs
probalog *twice* on each program: once with facts left unannotated
(probability 1) and once with every fact at `:: 0.5`. Same facts, same
rules, same fixpoint, same derived relation — the only difference is
whether the probabilities are trivial, which isolates what uncertainty
costs from every other factor.

**probalog derived exactly the relation Soufflé did, every time** —
across five program families and 20 configurations, up to 5461 tuples.
Since the suites include `sg` and Andersen's points-to, that is a
reasonable check against a mature engine.

The `cost of probability` is probalog@0.5 divided by probalog@1:

| suite          | relation | prob cost |
| -------------- | -------: | --------: |
| pointsto (16)  |      289 |  **1.0x** |
| sg (depth 6)   |     5461 |      1.1x |
| ring (60)      |     3600 |  **1.0x** |
| chordring (16) |      256 |      1.4x |
| chordring (20) |      400 |      2.8x |
| dag (6,6)      |      613 |      4.8x |

On chains, trees and program analysis, probability is free —
points-to, same-generation and the 60-node ring cost the same at 0.5
as at 1, even at 5461 tuples. Dense cyclic graphs and wide converging
DAGs are where it is paid for.

probalog@1 is otherwise flat and startup-dominated (~0.3s of it is
Racket booting). Soufflé runs at 0.04–0.06s here, also mostly startup;
`souffle -c` compiles to C++ and would widen the gap further.

## Reading the output

A query prints as a distribution over `#t` and `#f`:

```
Path("a", "c"): #<pmf: [#t 0.3] [#f 0.7]>
```

unless the answer is certain, in which case it prints as `#t` or `#f`
alone. So `#f` means "provably never derivable, given the facts, the
rules and every observation so far", not "probability rounded to zero".
