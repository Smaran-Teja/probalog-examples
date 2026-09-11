#!/usr/bin/env python3
"""Cross-system comparison: probalog against Scallop.

Scallop is the only system compared here that is *Datalog* rather than
Prolog. ProbLog and cplint both evaluate top-down and derive only what
a query needs; Scallop evaluates bottom-up and computes whole
relations, which is what probalog does. So this comparison has no
goal-direction confound to correct for -- there is no `--all-queries`
mode because Scallop is always in it.

Scallop attaches a provenance semiring to Datalog, and most of the
probabilistic ones are *not* exact:

  addmultprob     assumes derivations are independent, which is the
                  disjoint-sum error
  minmaxprob      fuzzy, not distribution semantics
  topkproofs      keeps only the k best proofs

`topkproofs` with a large enough k keeps every proof and compiles the
resulting formula to an SDD, which is exact. That is what this script
uses, and it is checked against known answers: a graph whose two
routes share their only uncertain edge comes out 0.5 rather than the
0.75 an independence assumption gives, and the Biomine network in
ported/problog-biomine.rkt comes out 0.415324 rather than 0.5569.

Programs come from compare-problog.py's generators, so all four
harnesses run the same models. The ProbLog form is translated to
Scallop rather than written twice.

Setup
-----

    git clone https://github.com/scallop-lang/scallop
    rustup toolchain install nightly       # scallop needs nightly
    cd scallop && cargo +nightly build --release --manifest-path etc/scli/Cargo.toml
    SCLI=.../target/release/scli ./bench/compare-scallop.sh

Usage
-----

    ./bench/compare-scallop.sh --quick
    ./bench/compare-scallop.sh ring smokers
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

SCLI = os.environ.get("SCLI", "scli")
RACKET = os.environ.get("RACKET", "racket")
# topkproofs keeps the k best proofs. A large k is not automatically
# better: the cost is proof enumeration, and on a dense cyclic program
# raising k past the point where the answer has already converged buys
# nothing while making the run explode -- the 8-node chorded ring is
# exact at k=10 in under a second and times out at k=100.
#
# So k is kept modest and exactness is *verified per row* by the agree
# column rather than assumed from k being huge. A row that reads NO is
# a row where this k was too small.
TOP_K = int(os.environ.get("SCALLOP_TOP_K", "10"))

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_problog_harness():
    path = os.path.join(HERE, "compare-problog.py")
    spec = importlib.util.spec_from_file_location("compare_problog", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CP = _load_problog_harness()


# --------------------------------------------------------------------------
# Translating the ProbLog form into Scallop
# --------------------------------------------------------------------------

ATOM = re.compile(r"(\w+)\(([^)]*)\)")
FACT = re.compile(r"^\s*(?:([0-9.]+)::)?(\w+)\(([^)]*)\)\.\s*$")
RULE = re.compile(r"^\s*(\w+)\(([^)]*)\)\s*:-\s*(.*)\.\s*$")
QUERY = re.compile(r"^\s*query\((\w+)\((.*)\)\)\.\s*$")


def scl_term(t):
    """A ProbLog argument as Scallop writes it.

    ProbLog variables are the capitalised identifiers; everything else
    is a constant. Scallop treats a bare lowercase identifier in a rule
    as a variable, so a constant has to be a number or a quoted string.
    """
    t = t.strip()
    if t[:1].isupper():          # X, Y, Z1 -- a variable
        return t.lower()
    try:
        float(t)
        return t                 # a number stays bare
    except ValueError:
        return f'"{t}"'          # an atom becomes a string


def to_scallop(problog_src):
    """Returns (scallop_source, queried_relation)."""
    facts = {}          # relation -> list of "p::(args)"
    rules = []
    queried = None

    for line in problog_src.splitlines():
        if not line.strip():
            continue
        m = QUERY.match(line)
        if m:
            queried = m.group(1)
            continue
        m = RULE.match(line)
        if m:
            head, head_args, body = m.group(1), m.group(2), m.group(3)
            conjuncts = [f"{n}({', '.join(scl_term(a) for a in args.split(','))})"
                         for n, args in ATOM.findall(body)]
            rules.append(f"rel {head}({', '.join(scl_term(a) for a in head_args.split(','))})"
                         f" = {' and '.join(conjuncts)}")
            continue
        m = FACT.match(line)
        if m:
            prob, name, args = m.group(1), m.group(2), m.group(3)
            prob = prob if prob is not None else "1.0"
            tup = ", ".join(scl_term(a) for a in args.split(","))
            facts.setdefault(name, []).append(f"{prob}::({tup})")
            continue
        raise ValueError(f"cannot translate: {line!r}")

    out = [f"rel {n} = {{{', '.join(ts)}}}" for n, ts in facts.items()]
    out += rules
    out.append(f"query {queried}")
    return "\n".join(out), queried


def scallop_value(out, relation, tup):
    """Pull one tuple's probability out of scli's relation dump."""
    if not out:
        return None
    # Scallop prints string constants quoted, so rebuild the tuple the
    # same way it was written into the program.
    want = "(" + ", ".join(scl_term(str(t)) for t in tup) + ")"
    # entries look like `0.3::(0, 2)`, separated by ", "
    for m in re.finditer(r"([0-9.eE+-]+)::\(([^)]*)\)", out):
        if "(" + m.group(2) + ")" == want:
            return float(m.group(1))
    return None


def query_tuple(problog_src):
    """The tuple the generated program asked about."""
    for line in problog_src.splitlines():
        m = QUERY.match(line)
        if m:
            return tuple(a.strip().strip('"') for a in m.group(2).split(","))
    return None


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


def run_suite(name, spec, args, tmpdir):
    sizes = spec["quick"] if args.quick else spec["sizes"]
    print(f"\n=== {name}: {spec['blurb']} ===")
    print(f"{'size':<12}{'Scallop':>10}{'probalog':>11}{'ratio':>9}  {'agree':<7}")

    for params in sizes:
        pl_src, rk_src = spec["gen"](*params)
        scl_src, relation = to_scallop(pl_src)
        tup = query_tuple(pl_src)

        scl = os.path.join(tmpdir, "m.scl")
        with open(scl, "w") as f:
            f.write(scl_src)
        ts, os_ = timed([SCLI, "-p", "topkproofs", "--top-k", str(TOP_K), scl],
                        args.timeout)

        rk = os.path.join(tmpdir, "m.rkt")
        with open(rk, "w") as f:
            f.write(rk_src)
        tr, orr = timed([RACKET, rk], args.timeout)

        vs = scallop_value(os_, relation, tup) if ts else None
        vr = CP.probalog_prob(orr) if tr else None
        if vs is not None and vr is not None:
            agree = "yes" if abs(vs - vr) < 1e-6 else "NO"
            val = f"{vs:.6f}"
        else:
            agree, val = "-", ""

        fmt = lambda t, why: (f"{t:8.2f}s" if t else f"{why:>9}")
        ratio = f"{tr / ts:7.1f}x" if (ts and tr) else "        -"
        print(f"{str(params):<12}{fmt(ts, os_):>10}{fmt(tr, orr):>11}"
              f"{ratio:>9}  {agree:<7}{val}")
        sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("suites", nargs="*", choices=list(CP.SUITES) + [])
    ap.add_argument("--quick", action="store_true", help="small sizes only")
    ap.add_argument("--timeout", type=float, default=10,
                    help="per-run timeout in seconds (default 10)")
    args = ap.parse_args()

    if shutil.which(RACKET) is None:
        sys.exit(f"racket not found (set RACKET=...): {RACKET}")
    if shutil.which(SCLI) is None and not os.path.exists(SCLI):
        sys.exit(f"scli not found (set SCLI=...): {SCLI}\n"
                 "  see the setup notes at the top of this file")

    print("probalog vs Scallop   provenance=topkproofs k=%d" % TOP_K)
    print("  Scallop computes the whole relation, as probalog does, so")
    print("  there is no goal-direction difference to correct for.")

    with tempfile.TemporaryDirectory() as tmpdir:
        for name in (args.suites or CP.SUITES):
            run_suite(name, CP.SUITES[name], args, tmpdir)


if __name__ == "__main__":
    main()
