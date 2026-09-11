#!/usr/bin/env python3
"""Cross-system comparison: probalog against ProbLog, on matched programs.

Each suite below generates the *same* probabilistic Datalog program in
both syntaxes, runs both systems, and reports the wall time and whether
they agreed on the answer. A third opinion is available from a Monte
Carlo simulation of the same model, which is what settles a
disagreement.

This is a Python script, in a repository of Racket examples, because
ProbLog is a Python package and has to be driven from one.

Setup
-----

    python3 -m venv /tmp/problog-venv
    /tmp/problog-venv/bin/pip install problog pysdd
    PROBLOG=/tmp/problog-venv/bin/problog python3 bench/compare-problog.py

`pysdd` matters. ProbLog's default knowledge compiler is dsharp, and on
cyclic programs it can return numbers that are not probabilities at all
-- the 16-node chorded ring below comes back as 13659.889 rather than
0.9387. The SDD backend gets it right, so this script passes `-k sdd`.
Run with `--backend ddnnf` to reproduce the bad answers.

Usage
-----

    python3 bench/compare-problog.py                 # every suite
    python3 bench/compare-problog.py --quick         # small sizes, fast
    python3 bench/compare-problog.py dag smokers     # named suites
    python3 bench/compare-problog.py --verify        # add Monte Carlo
"""

import argparse
import os
import random
import re
import shutil
import subprocess
import sys
import time

PROBLOG = os.environ.get("PROBLOG", "problog")
RACKET = os.environ.get("RACKET", "racket")

HEADER = "#lang roulette/example/probalog"


# --------------------------------------------------------------------------
# Program generators
#
# Each returns (problog_source, probalog_source) for the same model.
# ProbLog wants lowercase predicates and uppercase variables; probalog
# wants the reverse, with constants quoted.
# --------------------------------------------------------------------------

def _reach_pair(edges, target, p, nodes=None, all_queries=False):
    """Transitive closure over `edges`.

    With all_queries, both programs are asked for the *entire* reach
    relation rather than one tuple. That matters for fairness: probalog
    computes the whole relation whatever you ask it, while ProbLog
    derives only what the query needs. Comparing one probalog run
    against a single ProbLog query charges probalog for work its
    opponent never does.
    """
    pl = [f"{p}::edge({u},{v})." for u, v in edges]
    pl += ["reach(X,Y) :- edge(X,Y).",
           "reach(X,Z) :- reach(X,Y), edge(Y,Z)."]
    rk = [HEADER]
    rk += [f"Edge({u}, {v}) :: {p}." for u, v in edges]
    rk += ["Reach(x, y) :- Edge(x, y).",
           "Reach(x, z) :- Reach(x, y), Edge(y, z)."]
    if all_queries:
        ns = nodes if nodes is not None else sorted({n for e in edges for n in e})
        pl += [f"query(reach({i},{j}))." for i in ns for j in ns]
        rk += [f"? Reach({i}, {j})." for i in ns for j in ns]
    else:
        pl.append(f"query(reach({edges[0][0]},{target})).")
        rk.append(f"? Reach({edges[0][0]}, {target}).")
    return "\n".join(pl), "\n".join(rk)


def gen_ring(n, p=0.9, all_queries=False):
    """A simple directed cycle. Every derivation is a single path."""
    return _reach_pair([(i, (i + 1) % n) for i in range(n)], n // 2, p,
                       nodes=range(n), all_queries=all_queries)


def gen_chordring(n, chord=3, p=0.85, all_queries=False):
    """A cycle plus chords: dense, cyclic, facts re-derived many ways."""
    edges = [(i, (i + 1) % n) for i in range(n)]
    edges += [(i, (i + chord) % n) for i in range(n)]
    return _reach_pair(edges, n // 2, p, nodes=range(n),
                       all_queries=all_queries)


def gen_dag(layers, width, p=0.9, all_queries=False):
    """Layered DAG, fully connected between adjacent layers.

    width**layers distinct src->sink paths, all the same length, so
    this is many converging derivations with no cycles at all.
    """
    def node(l, i):
        return f"n{l}_{i}"
    edges = [("src", node(0, j)) for j in range(width)]
    for l in range(layers - 1):
        edges += [(node(l, a), node(l + 1, b))
                  for a in range(width) for b in range(width)]
    edges += [(node(layers - 1, j), "sink") for j in range(width)]
    pl = [f"{p}::edge({u},{v})." for u, v in edges]
    pl += ["path(X,Y) :- edge(X,Y).",
           "path(X,Z) :- path(X,Y), edge(Y,Z)."]
    rk = [HEADER]
    rk += [f'Edge("{u}", "{v}") :: {p}.' for u, v in edges]
    rk += ["Path(x, y) :- Edge(x, y).",
           "Path(x, z) :- Path(x, y), Edge(y, z)."]
    if all_queries:
        ns = sorted({n for e in edges for n in e})
        pl += [f"query(path({i},{j}))." for i in ns for j in ns]
        rk += [f'? Path("{i}", "{j}").' for i in ns for j in ns]
    else:
        pl.append("query(path(src,sink)).")
        rk.append('? Path("src", "sink").')
    return "\n".join(pl), "\n".join(rk)


def gen_smokers(n, pstress=0.2, pinf=0.3, all_queries=False):
    """Friends & smokers on a friendship ring: recursion around cycles."""
    pl, rk = [], []
    for i in range(n):
        pl.append(f"{pstress}::stress(p{i}).")
        rk.append(f'Stress("p{i}") :: {pstress}.')
    for i in range(n):
        j = (i + 1) % n
        pl += [f"friend(p{i},p{j}).", f"friend(p{j},p{i}).",
               f"{pinf}::influences(p{i},p{j}).",
               f"{pinf}::influences(p{j},p{i})."]
        rk += [f'Friend("p{i}", "p{j}").', f'Friend("p{j}", "p{i}").',
               f'Influences("p{i}", "p{j}") :: {pinf}.',
               f'Influences("p{j}", "p{i}") :: {pinf}.']
    pl += ["smokes(X) :- stress(X).",
           "smokes(X) :- friend(X,Y), smokes(Y), influences(Y,X)."]
    rk = [HEADER] + rk + [
        "Smokes(x) :- Stress(x).",
        "Smokes(x) :- Friend(x, y), Smokes(y), Influences(y, x)."]
    if all_queries:
        pl += [f"query(smokes(p{i}))." for i in range(n)]
        rk += [f'? Smokes("p{i}").' for i in range(n)]
    else:
        pl.append("query(smokes(p0)).")
        rk.append('? Smokes("p0").')
    return "\n".join(pl), "\n".join(rk)


# --------------------------------------------------------------------------
# Monte Carlo, for arbitrating a disagreement
# --------------------------------------------------------------------------

def mc_reach(edges, source, target, p, trials):
    hits = 0
    for _ in range(trials):
        adj = {}
        for u, v in edges:
            if random.random() < p:
                adj.setdefault(u, []).append(v)
        seen, stack = {source}, [source]
        while stack:
            u = stack.pop()
            if u == target:
                hits += 1
                break
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
    return hits / trials


def mc_smokers(n, trials, pstress=0.2, pinf=0.3):
    hits = 0
    for _ in range(trials):
        smokes = {i for i in range(n) if random.random() < pstress}
        infl = {}
        for i in range(n):
            j = (i + 1) % n
            infl[(i, j)] = random.random() < pinf
            infl[(j, i)] = random.random() < pinf
        changed = True
        while changed:                       # least fixpoint
            changed = False
            for i in range(n):
                if i in smokes:
                    continue
                for j in ((i + 1) % n, (i - 1) % n):
                    if j in smokes and infl.get((j, i)):
                        smokes.add(i)
                        changed = True
                        break
        hits += 0 in smokes
    return hits / trials


# --------------------------------------------------------------------------
# Suites
# --------------------------------------------------------------------------

SUITES = {
    "ring": dict(
        blurb="directed cycle, one path per derivation",
        gen=gen_ring,
        sizes=[(6,), (10,), (14,), (20,)],
        quick=[(6,), (10,)],
        mc=lambda n, t: mc_reach([(i, (i + 1) % n) for i in range(n)],
                                 0, n // 2, 0.9, t)),
    "chordring": dict(
        blurb="cycle + chords: dense and cyclic",
        gen=gen_chordring,
        sizes=[(8,), (10,), (12,), (14,), (16,)],
        quick=[(8,), (12,)],
        mc=lambda n, t: mc_reach([(i, (i + 1) % n) for i in range(n)]
                                 + [(i, (i + 3) % n) for i in range(n)],
                                 0, n // 2, 0.85, t)),
    "dag": dict(
        blurb="layered DAG: many converging derivations, no cycles",
        gen=gen_dag,
        sizes=[(6, 4), (7, 4), (6, 5), (7, 5), (6, 6)],
        quick=[(4, 3), (6, 4)],
        mc=None),
    "smokers": dict(
        blurb="friends & smokers: recursion around a cyclic relation",
        gen=gen_smokers,
        sizes=[(10,), (12,), (13,), (14,), (15,)],
        quick=[(8,), (12,)],
        mc=lambda n, t: mc_smokers(n, t)),
}


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------

def problog_prob(out):
    if not out or not out.strip():
        return None
    m = re.search(r":\s*([0-9.eE+-]+)\s*$", out.strip().splitlines()[-1])
    return float(m.group(1)) if m else None


def probalog_prob(out):
    """probalog prints a pmf, or bare #t / #f when the answer is certain."""
    if not out or not out.strip():
        return None
    last = out.strip().splitlines()[-1]
    m = re.search(r"#t ([0-9.eE+-]+)", last)
    if m:
        return float(m.group(1))
    if last.endswith(": #t"):
        return 1.0
    if last.endswith(": #f"):
        return 0.0
    return None


def timed(cmd, timeout):
    """Returns (seconds, stdout) or (None, reason)."""
    t0 = time.perf_counter()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"
    except FileNotFoundError:
        return None, "NOT FOUND"
    if r.returncode != 0:
        return None, "ERROR"
    return time.perf_counter() - t0, r.stdout


def run_suite(name, spec, args, tmpdir):
    sizes = spec["quick"] if args.quick else spec["sizes"]
    print(f"\n=== {name}: {spec['blurb']} ===")
    cols = f"{'size':<12}{'ProbLog':>10}{'probalog':>11}{'ratio':>9}  {'agree':<7}"
    print(cols + ("  monte carlo" if args.verify and spec["mc"] else ""))

    for params in sizes:
        pl_src, rk_src = spec["gen"](*params, all_queries=args.all_queries)
        pl_path = os.path.join(tmpdir, "m.pl")
        rk_path = os.path.join(tmpdir, "m.rkt")
        with open(pl_path, "w") as f:
            f.write(pl_src)
        with open(rk_path, "w") as f:
            f.write(rk_src)

        tp, op = timed([PROBLOG, "-k", args.backend, pl_path], args.timeout)
        tr, orr = timed([RACKET, rk_path], args.timeout)
        # With every tuple queried the output is a table, not one
        # answer, so the single-answer agreement check does not apply.
        vp = None if args.all_queries else (problog_prob(op) if tp else None)
        vr = None if args.all_queries else (probalog_prob(orr) if tr else None)

        if vp is not None and vr is not None:
            agree = "yes" if abs(vp - vr) < 1e-6 else "NO"
        else:
            agree = "-"
        shown = vp if vp is not None else vr
        val = f"{shown:.6f}" if shown is not None else ""

        fmt = lambda t, why: (f"{t:8.2f}s" if t else f"{why:>9}")
        ratio = f"{tr / tp:7.1f}x" if (tp and tr and tp > 0) else "        -"
        line = (f"{str(params):<12}{fmt(tp, op):>10}{fmt(tr, orr):>11}"
                f"{ratio:>9}  {agree:<7}{val}")

        if args.verify and spec["mc"]:
            mcv = spec["mc"](*params, args.trials)
            line += f"   mc={mcv:.4f}"
        print(line)
        sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("suites", nargs="*", choices=list(SUITES) + [],
                    help="suites to run (default: all)")
    ap.add_argument("--quick", action="store_true",
                    help="small sizes only, for a fast sanity run")
    ap.add_argument("--timeout", type=float, default=10,
                    help="per-run timeout in seconds (default 10)")
    ap.add_argument("--backend", default="sdd",
                    help="ProbLog knowledge compiler; 'ddnnf' reproduces "
                         "the wrong answers noted above (default sdd)")
    ap.add_argument("--all-queries", action="store_true",
                    help="ask both systems for the entire relation, not one "
                         "tuple. probalog computes it all regardless, so "
                         "this is the equal-work comparison")
    ap.add_argument("--verify", action="store_true",
                    help="also estimate each answer by Monte Carlo")
    ap.add_argument("--trials", type=int, default=200000,
                    help="Monte Carlo trials (default 200000)")
    args = ap.parse_args()

    if shutil.which(RACKET) is None:
        sys.exit(f"racket not found (set RACKET=...): {RACKET}")
    if shutil.which(PROBLOG) is None and not os.path.exists(PROBLOG):
        sys.exit(f"problog not found (set PROBLOG=...): {PROBLOG}\n"
                 "  python3 -m venv /tmp/problog-venv\n"
                 "  /tmp/problog-venv/bin/pip install problog pysdd")

    print(f"probalog vs ProbLog   ProbLog backend={args.backend}  "
          f"timeout={args.timeout}s")
    print("wall clock includes interpreter startup: ~0.3s racket, ~0.1s problog,")
    print("so anything under a second or so is noise.")

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        for name in (args.suites or SUITES):
            run_suite(name, SUITES[name], args, tmpdir)


if __name__ == "__main__":
    main()
