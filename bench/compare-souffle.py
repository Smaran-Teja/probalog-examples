#!/usr/bin/env python3
"""Cross-system comparison: probalog against Souffle, on matched programs.

Souffle is a pure Datalog engine with no notion of probability, so the
comparison runs probalog *twice* on each program:

  probalog@1     every fact declared with no annotation, so probability
                 1 -- plain Datalog, directly comparable to Souffle.

  probalog@0.5   every fact annotated `:: 0.5`. Same facts, same rules,
                 same derived relation, but the probabilities are no
                 longer trivial.

The gap between Souffle and probalog@1 is the cost of running an
interpreter in Racket against compiled C++. The gap between probalog@1
and probalog@0.5 isolates what uncertainty costs from every other
factor, which is the number this comparison is for.

Both systems compute the whole relation, so the work compared is the
same.

Setup
-----

    brew install souffle          # or see souffle-lang.github.io

Usage
-----

    ./bench/compare-souffle.sh              # every suite
    ./bench/compare-souffle.sh --quick      # small sizes
    ./bench/compare-souffle.sh sg pointsto  # named suites
"""

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

SOUFFLE = os.environ.get("SOUFFLE", "souffle")
RACKET = os.environ.get("RACKET", "racket")
HEADER = "#lang roulette/example/probalog"


# --------------------------------------------------------------------------
# Emitting the three program forms
# --------------------------------------------------------------------------

def sf_const(x):
    return f'"{x}"' if isinstance(x, str) else str(x)


def rk_const(x):
    return f'"{x}"' if isinstance(x, str) else str(x)


def souffle_program(decls, facts, rules, output):
    """decls: [(name, [types])], facts: [(name, [args])], rules: [str]."""
    out = [f".decl {n}({', '.join(f'a{i}:{t}' for i, t in enumerate(ts))})"
           for n, ts in decls]
    out.append(f".output {output}")
    out += [f"{n}({','.join(sf_const(a) for a in args)})." for n, args in facts]
    out += rules
    return "\n".join(out)


# Souffle relation names are lowercase; probalog requires predicate names
# to start with a capital. The facts are generated once and emitted into
# both syntaxes, so the names are translated on the way out.
NAMES = {
    "edge": "Edge", "reach": "Reach", "path": "Path",
    "up": "Up", "down": "Down", "flat": "Flat", "sg": "SameGen",
    "addressof": "AddressOf", "assign": "Assign", "store": "Store",
    "load": "Load", "varpointsto": "VarPointsTo",
    "fieldpointsto": "FieldPointsTo",
}


def probalog_program(facts, rules, query, prob):
    """prob=None means no annotation at all, i.e. probability 1."""
    ann = "." if prob is None else f" :: {prob}."
    out = [HEADER]
    out += [f"{NAMES.get(n, n.capitalize())}"
            f"({', '.join(rk_const(a) for a in args)}){ann}"
            for n, args in facts]
    out += rules
    out.append(f"? {query}.")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Program families
#
# Each returns (decls, facts, souffle_rules, probalog_rules, output_rel,
#               query_string, query_tuple).
# --------------------------------------------------------------------------

def fam_ring(n):
    facts = [("edge", [i, (i + 1) % n]) for i in range(n)]
    tgt = n // 2
    return (
        [("edge", ["number"] * 2), ("reach", ["number"] * 2)],
        facts,
        ["reach(x,y) :- edge(x,y).",
         "reach(x,z) :- reach(x,y), edge(y,z)."],
        ["Reach(x, y) :- Edge(x, y).",
         "Reach(x, z) :- Reach(x, y), Edge(y, z)."],
        "reach", f"Reach(0, {tgt})", ("0", str(tgt)))


def fam_chordring(n, chord=3):
    facts = [("edge", [i, (i + 1) % n]) for i in range(n)]
    facts += [("edge", [i, (i + chord) % n]) for i in range(n)]
    tgt = n // 2
    return (
        [("edge", ["number"] * 2), ("reach", ["number"] * 2)],
        facts,
        ["reach(x,y) :- edge(x,y).",
         "reach(x,z) :- reach(x,y), edge(y,z)."],
        ["Reach(x, y) :- Edge(x, y).",
         "Reach(x, z) :- Reach(x, y), Edge(y, z)."],
        "reach", f"Reach(0, {tgt})", ("0", str(tgt)))


def fam_dag(layers, width):
    def node(l, i):
        return f"n{l}_{i}"
    e = [("edge", ["src", node(0, j)]) for j in range(width)]
    for l in range(layers - 1):
        e += [("edge", [node(l, a), node(l + 1, b)])
              for a in range(width) for b in range(width)]
    e += [("edge", [node(layers - 1, j), "sink"]) for j in range(width)]
    return (
        [("edge", ["symbol"] * 2), ("path", ["symbol"] * 2)],
        e,
        ["path(x,y) :- edge(x,y).",
         "path(x,z) :- path(x,y), edge(y,z)."],
        ["Path(x, y) :- Edge(x, y).",
         "Path(x, z) :- Path(x, y), Edge(y, z)."],
        "path", 'Path("src", "sink")', ("src", "sink"))


def fam_sg(depth, branch=2):
    """Same generation over a balanced tree -- the classic benchmark."""
    facts, nodes, frontier = [], ["r"], ["r"]
    for d in range(depth):
        nxt = []
        for p in frontier:
            for b in range(branch):
                c = f"{p}{b}"
                facts.append(("up", [c, p]))
                nodes.append(c)
                nxt.append(c)
        frontier = nxt
    facts.append(("flat", ["r", "r"]))
    deepest = frontier[0]
    other = frontier[-1]
    return (
        [("up", ["symbol"] * 2), ("flat", ["symbol"] * 2),
         ("down", ["symbol"] * 2), ("sg", ["symbol"] * 2)],
        facts,
        ["down(p,c) :- up(c,p).",
         "sg(x,y) :- flat(x,y).",
         "sg(x,y) :- up(x,z1), sg(z1,z2), down(z2,y)."],
        ["Down(p, c) :- Up(c, p).",
         "SameGen(x, y) :- Flat(x, y).",
         "SameGen(x, y) :- Up(x, z1), SameGen(z1, z2), Down(z2, y)."],
        "sg", f'SameGen("{deepest}", "{other}")', (deepest, other))


def fam_pointsto(n):
    """Andersen's points-to on a synthetic chain of assignments."""
    facts = [("addressof", [f"v0", "o0"])]
    for i in range(n):
        facts.append(("assign", [f"v{i+1}", f"v{i}"]))
        facts.append(("addressof", [f"w{i}", f"o{i+1}"]))
        facts.append(("store", [f"v{i}", "f", f"w{i}"]))
        facts.append(("load", [f"u{i}", f"v{i+1}", "f"]))
    return (
        [("addressof", ["symbol"] * 2), ("assign", ["symbol"] * 2),
         ("store", ["symbol"] * 3), ("load", ["symbol"] * 3),
         ("varpointsto", ["symbol"] * 2), ("fieldpointsto", ["symbol"] * 3)],
        facts,
        ["varpointsto(v,o) :- addressof(v,o).",
         "varpointsto(v,o) :- assign(v,u), varpointsto(u,o).",
         "varpointsto(v,o) :- load(v,u,f), varpointsto(u,b), fieldpointsto(b,f,o).",
         "fieldpointsto(b,f,o) :- store(u,f,v), varpointsto(u,b), varpointsto(v,o)."],
        ["VarPointsTo(v, o) :- AddressOf(v, o).",
         "VarPointsTo(v, o) :- Assign(v, u), VarPointsTo(u, o).",
         "VarPointsTo(v, o) :- Load(v, u, f), VarPointsTo(u, b), FieldPointsTo(b, f, o).",
         "FieldPointsTo(b, f, o) :- Store(u, f, v), VarPointsTo(u, b), VarPointsTo(v, o)."],
        "varpointsto", f'VarPointsTo("v{n}", "o0")', (f"v{n}", "o0"))


SUITES = {
    "ring": dict(blurb="directed cycle", fam=fam_ring,
                 sizes=[(10,), (20,), (40,), (60,)], quick=[(10,), (20,)]),
    "chordring": dict(blurb="cycle + chords: dense and cyclic", fam=fam_chordring,
                      sizes=[(8,), (12,), (16,), (20,)], quick=[(8,), (12,)]),
    "dag": dict(blurb="layered DAG: many converging derivations", fam=fam_dag,
                sizes=[(4, 3), (6, 4), (6, 5), (6, 6)], quick=[(4, 3), (6, 4)]),
    "sg": dict(blurb="same generation over a balanced tree", fam=fam_sg,
               sizes=[(3,), (4,), (5,), (6,)], quick=[(3,), (4,)]),
    "pointsto": dict(blurb="Andersen's points-to analysis", fam=fam_pointsto,
                     sizes=[(4,), (8,), (12,), (16,)], quick=[(4,), (8,)]),
}


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------

def timed(cmd, timeout, cwd=None):
    t0 = time.perf_counter()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"
    except FileNotFoundError:
        return None, "NOT FOUND"
    if r.returncode != 0:
        return None, "ERROR"
    return time.perf_counter() - t0, r.stdout


def probalog_answer(out):
    """#t / #f, or the probability that the queried fact holds."""
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


def souffle_tuples(outdir, relation):
    path = os.path.join(outdir, f"{relation}.csv")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return {tuple(row) for row in csv.reader(f, delimiter="\t") if row}


def run_suite(name, spec, args, tmpdir):
    sizes = spec["quick"] if args.quick else spec["sizes"]
    print(f"\n=== {name}: {spec['blurb']} ===")
    print(f"{'size':<12}{'Souffle':>10}{'probalog@1':>13}{'probalog@0.5':>15}"
          f"{'prob cost':>11}  {'agree':<7}{'|rel|':>8}")

    for params in sizes:
        decls, facts, sf_rules, rk_rules, outrel, query, qtuple = spec["fam"](*params)

        dl = os.path.join(tmpdir, "m.dl")
        with open(dl, "w") as f:
            f.write(souffle_program(decls, facts, sf_rules, outrel))
        outdir = os.path.join(tmpdir, "out")
        shutil.rmtree(outdir, ignore_errors=True)
        os.makedirs(outdir, exist_ok=True)
        ts, _ = timed([SOUFFLE, "-D", outdir, dl], args.timeout)
        tuples = souffle_tuples(outdir, outrel) if ts else None

        rk1 = os.path.join(tmpdir, "one.rkt")
        with open(rk1, "w") as f:
            f.write(probalog_program(facts, rk_rules, query, None))
        t1, o1 = timed([RACKET, rk1], args.timeout)

        rkh = os.path.join(tmpdir, "half.rkt")
        with open(rkh, "w") as f:
            f.write(probalog_program(facts, rk_rules, query, 0.5))
        th, oh = timed([RACKET, rkh], args.timeout)

        # probalog@1 should say #t for exactly the tuples Souffle derived.
        v1 = probalog_answer(o1) if t1 else None
        if tuples is not None and v1 is not None:
            expected = 1.0 if qtuple in tuples else 0.0
            agree = "yes" if abs(v1 - expected) < 1e-9 else "NO"
        else:
            agree = "-"

        fmt = lambda t, why: (f"{t:8.2f}s" if t else f"{why:>9}")
        cost = f"{th / t1:8.1f}x" if (t1 and th) else "        -"
        size = f"{len(tuples):>8}" if tuples is not None else "       -"
        print(f"{str(params):<12}{fmt(ts, 'ERR'):>10}{fmt(t1, o1):>13}"
              f"{fmt(th, oh):>15}{cost:>11}  {agree:<7}{size}")
        sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("suites", nargs="*", choices=list(SUITES) + [])
    ap.add_argument("--quick", action="store_true", help="small sizes only")
    ap.add_argument("--timeout", type=float, default=10,
                    help="per-run timeout in seconds (default 10)")
    args = ap.parse_args()

    if shutil.which(RACKET) is None:
        sys.exit(f"racket not found (set RACKET=...): {RACKET}")
    if shutil.which(SOUFFLE) is None:
        sys.exit(f"souffle not found (set SOUFFLE=...): {SOUFFLE}\n"
                 "  brew install souffle")

    print("probalog vs Souffle")
    print("  probalog@1    facts with no annotation: plain Datalog")
    print("  probalog@0.5  every fact :: 0.5: same relation, uncertain")
    print("  prob cost     probalog@0.5 / probalog@1, the price of uncertainty")
    print("Souffle runs interpreted; `souffle -c` compiles to C++ and is faster")
    print("still. Racket startup is ~0.3s, Souffle's ~0.02s, so sub-second")
    print("numbers are mostly startup.")

    with tempfile.TemporaryDirectory() as tmpdir:
        for name in (args.suites or SUITES):
            run_suite(name, SUITES[name], args, tmpdir)


if __name__ == "__main__":
    main()
