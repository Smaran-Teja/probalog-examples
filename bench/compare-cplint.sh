#!/usr/bin/env bash
#
# Install cplint into SWI-Prolog if needed, then run compare-cplint.py.
#
# The pack install is idempotent -- it is skipped once library(pita)
# loads -- so only the first run pays for it. Any arguments are passed
# straight through.
#
#   ./bench/compare-cplint.sh --quick
#   ./bench/compare-cplint.sh ring smokers --all-queries
#   ./bench/compare-cplint.sh --reinstall

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
script="$here/compare-cplint.py"

note() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

reinstall=0
args=()
for a in "$@"; do
  if [[ "$a" == "--reinstall" ]]; then reinstall=1; else args+=("$a"); fi
done

[[ -f "$script" ]] || die "cannot find $script"
command -v python3 >/dev/null || die "python3 not found"

swipl_cmd="${SWIPL:-swipl}"
if ! command -v "$swipl_cmd" >/dev/null; then
  hint="see https://www.swi-prolog.org/Download.html"
  command -v brew >/dev/null && hint="brew install swi-prolog"
  die "swipl not found (set SWIPL=... if it is installed elsewhere)

  $hint"
fi

racket_cmd="${RACKET:-racket}"
command -v "$racket_cmd" >/dev/null \
  || die "racket not found (set RACKET=... if it is installed elsewhere)

  probalog itself must be installed for the comparison to mean anything:
    raco pkg install --auto roulette/ roulette-lib/"

# --- cplint --------------------------------------------------------------

# library(pita) loading is the real test: the pack pulls in bddem, whose
# foreign BDD library has to have built for this architecture.
has_pita() {
  "$swipl_cmd" -g "use_module(library(pita))" -t halt >/dev/null 2>&1
}

if [[ $reinstall -eq 1 ]] || ! has_pita; then
  note "installing the cplint pack (first run only; pulls in bddem)"
  upgrade=false
  [[ $reinstall -eq 1 ]] && upgrade=true
  "$swipl_cmd" -g "pack_install(cplint,[interactive(false),upgrade($upgrade)])" \
               -t halt 2>&1 | sed 's/^/    /' || true
  has_pita || die "cplint installed but library(pita) still will not load.
  The bddem pack builds a native BDD library; check its build output above."
fi

note "$("$swipl_cmd" --version 2>&1 | head -1) with cplint/PITA"
note "running compare-cplint.py ${args[*]:-}"
echo

SWIPL="$swipl_cmd" RACKET="$racket_cmd" \
  exec python3 "$script" ${args[@]+"${args[@]}"}
