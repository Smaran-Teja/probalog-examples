#!/usr/bin/env bash
#
# Check that Scallop's scli is available, then run compare-scallop.py.
#
# Scallop is a Rust project needing a nightly toolchain, so this does
# not try to build it for you -- it points at the build if it cannot
# find one. Set SCLI to the binary, or put it on PATH.
#
#   ./bench/compare-scallop.sh --quick
#   SCLI=/path/to/scli ./bench/compare-scallop.sh ring smokers

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
script="$here/compare-scallop.py"

note() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

[[ -f "$script" ]] || die "cannot find $script"
command -v python3 >/dev/null || die "python3 not found"

scli_cmd="${SCLI:-scli}"
if ! command -v "$scli_cmd" >/dev/null && [[ ! -x "$scli_cmd" ]]; then
  die "scli not found (set SCLI=... to point at it)

  git clone https://github.com/scallop-lang/scallop
  rustup toolchain install nightly
  cd scallop
  cargo +nightly build --release --manifest-path etc/scli/Cargo.toml
  # binary lands at target/release/scli"
fi

racket_cmd="${RACKET:-racket}"
command -v "$racket_cmd" >/dev/null \
  || die "racket not found (set RACKET=... if it is installed elsewhere)

  probalog itself must be installed for the comparison to mean anything:
    raco pkg install --auto roulette/ roulette-lib/"

note "$("$scli_cmd" --version 2>&1 | head -1 || echo 'scallop scli')"
note "running compare-scallop.py ${*:-}"
echo

SCLI="$scli_cmd" RACKET="$racket_cmd" exec python3 "$script" "$@"
