#!/usr/bin/env python3
"""Cross-system comparison: probalog against cplint/PITA.

Two differences to keep in mind when reading the numbers:

  * cplint is Prolog, not Datalog. Every program here is in the
    function-free fragment, so this does not bias the comparison, but
    PITA is solving a more general problem than it needs to.

  * PITA is goal-directed: it derives only what the query needs, while
    probalog computes the entire relation whatever you ask it.
    Comparing one probalog run against a single PITA query therefore
    charges probalog for work PITA never does. Pass --all-queries for
    the equal-work comparison, where both are asked for the entire
    relation.

The program families are imported from compare-problog.py so that all
three harnesses run byte-identical models. LPAD syntax for
probabilistic facts is the same as ProbLog's, so only the preamble and
the way queries are posed differ.

Setup
-----

    brew install swi-prolog
    swipl -g "pack_install(cplint,[interactive(false)])" -t halt

Usage
-----

    ./bench/compare-cplint.sh --quick
    ./bench/compare-cplint.sh ring smokers --all-queries
"""

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

SWIPL = os.environ.get("SWIPL", "swipl")
RACKET = os.environ.get("RACKET", "racket")

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_problog_harness():
    """Reuse the program generators, so all three comparisons match."""
    path = os.path.join(HERE, "compare-problog.py")
    spec = importlib.util.spec_from_file_location("compare_problog", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CP = _load_problog_harness()

PREAMBLE = [":- use_module(library(pita)).", ":- pita.", ":- begin_lpad."]


# --------------------------------------------------------------------------
# Turning a ProbLog program into an LPAD
# --------------------------------------------------------------------------

def to_lpad(problog_src):
    """Strip query/2 directives and wrap the rest in an LPAD block.

    ProbLog and cplint share the `p::fact.` annotation syntax, so the
    body of the program carries over unchanged; only how you ask for a
    probability differs.
    """
    body = [l for l in problog_src.splitlines()
            if l.strip() and not l.strip().startswith("query(")]
    return "\n".join(PREAMBLE + body + [":- end_lpad."])


def problog_queries(problog_src):
    """The goals a generated program asked for, as Prolog terms."""
    out = []
    for line in problog_src.splitlines():
        m = re.match(r"\s*query\((.*)\)\.\s*$", line)
        if m:
            out.append(m.group(1))
    return out


def pita_goal(goals):
    """A swipl goal that prints one probability per line."""
    listed = "[" + ",".join(goals) + "]"
    return (f"forall(member(G,{listed}),"
            f"((prob(G,P)->true;P=0.0),format('~w~n',[P])))")


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------

def timed(cmd, timeout):
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


def first_float(text):
    for line in (text or "").splitlines():
        try:
            return float(line.strip())
        except ValueError:
            continue
    return None


def run_suite(name, spec, args, tmpdir):
    sizes = spec["quick"] if args.quick else spec["sizes"]
    print(f"\n=== {name}: {spec['blurb']} ===")
    print(f"{'size':<12}{'PITA':>10}{'probalog':>11}{'ratio':>9}  {'agree':<7}")

    for params in sizes:
        pl_src, rk_src = spec["gen"](*params, all_queries=args.all_queries)

        lpad = os.path.join(tmpdir, "m.pl")
        with open(lpad, "w") as f:
            f.write(to_lpad(pl_src))
        goals = problog_queries(pl_src)
        goal = f"consult('{lpad}'), {pita_goal(goals)}"
        tc, oc = timed([SWIPL, "-g", goal, "-t", "halt"], args.timeout)

        rk = os.path.join(tmpdir, "m.rkt")
        with open(rk, "w") as f:
            f.write(rk_src)
        tr, orr = timed([RACKET, rk], args.timeout)

        if args.all_queries:
            agree, val = "-", ""
        else:
            vc = first_float(oc) if tc else None
            vr = CP.probalog_prob(orr) if tr else None
            if vc is not None and vr is not None:
                agree = "yes" if abs(vc - vr) < 1e-6 else "NO"
                val = f"{vc:.6f}"
            else:
                agree, val = "-", ""

        fmt = lambda t, why: (f"{t:8.2f}s" if t else f"{why:>9}")
        ratio = f"{tr / tc:7.1f}x" if (tc and tr) else "        -"
        print(f"{str(params):<12}{fmt(tc, oc):>10}{fmt(tr, orr):>11}"
              f"{ratio:>9}  {agree:<7}{val}")
        sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("suites", nargs="*", choices=list(CP.SUITES) + [])
    ap.add_argument("--quick", action="store_true", help="small sizes only")
    ap.add_argument("--all-queries", action="store_true",
                    help="ask both for the entire relation, not one tuple")
    ap.add_argument("--timeout", type=float, default=10,
                    help="per-run timeout in seconds (default 10)")
    args = ap.parse_args()

    if shutil.which(RACKET) is None:
        sys.exit(f"racket not found (set RACKET=...): {RACKET}")
    if shutil.which(SWIPL) is None:
        sys.exit(f"swipl not found (set SWIPL=...): {SWIPL}\n"
                 "  brew install swi-prolog")

    print("probalog vs cplint/PITA")
    if not args.all_queries:
        print("  NOTE: PITA answers one query; probalog computes the whole")
        print("        relation. Pass --all-queries for the equal-work run.")

    with tempfile.TemporaryDirectory() as tmpdir:
        for name in (args.suites or CP.SUITES):
            run_suite(name, CP.SUITES[name], args, tmpdir)


if __name__ == "__main__":
    main()
