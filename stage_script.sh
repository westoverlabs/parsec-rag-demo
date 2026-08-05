#!/usr/bin/env bash
# stage_script.sh -- the whole demo as one clean, colour-coded run, for the stage.
#
#     ./stage_script.sh                     # run it, pausing between beats
#     ./stage_script.sh --no-pause          # run straight through (rehearsal)
#     ./stage_script.sh --model gpt-oss:20b-cloud
#
# Four beats, each with its own banner colour so the room can see which one they
# are in without you narrating the mechanics:
#
#     1  GROUNDED, TRUE          (green)   real questions, answered from the KB
#     2  POISONING THE SOURCE    (yellow)  swap one true fact for a plausible lie
#     3  SAME QUESTION, POISONED (red)     watch it repeat the lie, confidently
#     4  RESET                   (blue)    put it back, prove the truth returns
#
# It pauses before each beat so you can talk over it; press Enter to fire.
# --no-pause turns it into a straight end-to-end regression run.
#
# This is the SHORT stage version -- the four beats that carry the argument.
# rehearse.sh runs the fuller 13-step script including the .rag_off toggle and
# the live add-a-fact. Both share the same underlying scripts, so neither drifts.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

MODEL="${MODEL:-llama3.2}"
PAUSE=1

while [ $# -gt 0 ]; do
  case "$1" in
    --model) MODEL="${2:?--model needs a value}"; shift 2 ;;
    --no-pause) PAUSE=0; shift ;;
    # Print the header comment block, stopping at the first line of real code,
    # so this never drifts out of sync with a line number.
    -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/,""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)" >&2; exit 1 ;;
  esac
done

# Colour only when stdout is a terminal that can show it, so piping to a file or
# a dumb terminal produces clean plain text instead of escape-code soup.
if [ -t 1 ] && [ "${TERM:-dumb}" != "dumb" ] && command -v tput >/dev/null 2>&1 \
   && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
  BOLD=$(tput bold); RESET=$(tput sgr0)
  GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3)
  RED=$(tput setaf 1); BLUE=$(tput setaf 4); DIM=$(tput setaf 8 2>/dev/null || echo "")
else
  BOLD=""; RESET=""; GREEN=""; YELLOW=""; RED=""; BLUE=""; DIM=""
fi

WIDTH=74
rule() { printf '%s%s%s\n' "$1" "$(printf '=%.0s' $(seq 1 $WIDTH))" "$RESET"; }

banner() { # colour, number, title, subtitle
  local colour="$1" num="$2" title="$3" sub="$4"
  printf '\n'
  rule "$colour$BOLD"
  printf '%s%s  BEAT %s -- %s%s\n' "$colour" "$BOLD" "$num" "$title" "$RESET"
  printf '%s  %s%s\n' "$colour" "$sub" "$RESET"
  rule "$colour$BOLD"
}

pause() {
  [ "$PAUSE" = "1" ] || return 0
  printf '\n%s      [Enter] to continue%s' "$DIM" "$RESET"
  read -r _ || true
  printf '\n'
}

ask() {
  local q="$1"
  printf '\n%s  ?  %s%s\n\n' "$BOLD" "$q" "$RESET"
  if ! opencode run --agent astro --model "ollama/$MODEL" "$q" 2>&1 | sed 's/^/     /'; then
    printf '     %s(that turn failed -- ask again)%s\n' "$RED" "$RESET"
  fi
}

command -v opencode >/dev/null 2>&1 \
  || { echo "opencode not found. Run ./start_tui_demo.sh --check first." >&2; exit 1; }

printf '\n%s%s  PARSEC -- RAG grounding, live%s\n' "$BOLD" "$BLUE" "$RESET"
printf '%s  model: %s   knowledge base: astro_kg.json%s\n' "$DIM" "$MODEL" "$RESET"

./reset_demo.sh >/dev/null 2>&1
printf '%s  starting from a clean knowledge base%s\n' "$DIM" "$RESET"

# ---------------------------------------------------------------- BEAT 1
banner "$GREEN" 1 "GROUNDED, TRUE" \
  "The model answers from our verified astronomy facts."
pause
ask "What causes the Kirkwood gaps?"
pause
ask "Why do we use proper elements to find asteroid families?"

# ---------------------------------------------------------------- BEAT 2
banner "$YELLOW" 2 "POISONING THE SOURCE OF TRUTH" \
  "One true fact, replaced with a plausible-sounding falsehood."
pause
./poison_kb.sh

# ---------------------------------------------------------------- BEAT 3
banner "$RED" 3 "SAME QUESTION, POISONED KNOWLEDGE BASE" \
  "Same model, same question. Only the source changed."
pause
ask "What causes the Kirkwood gaps?"
printf '\n%s%s  It did not hedge. Grounding is a TRUST mechanism, not a TRUTH one:%s\n' \
  "$RED" "$BOLD" "$RESET"
printf '%s  it moves authority into your knowledge base -- so curating that base%s\n' "$RED" "$RESET"
printf '%s  is now part of the science.%s\n' "$RED" "$RESET"

# ---------------------------------------------------------------- BEAT 4
banner "$BLUE" 4 "RESET" \
  "Restore the knowledge base and show the truth come back."
pause
./reset_demo.sh
ask "What causes the Kirkwood gaps?"

printf '\n'
rule "$BLUE$BOLD"
if git diff --quiet -- astro_kg.json && [ ! -e .rag_off ]; then
  printf '%s%s  Knowledge base clean. Ready to run again.%s\n' "$BLUE" "$BOLD" "$RESET"
else
  printf '%s%s  WARNING: state left behind -- run ./reset_demo.sh%s\n' "$RED" "$BOLD" "$RESET"
  rule "$BLUE$BOLD"
  exit 1
fi
rule "$BLUE$BOLD"
printf '\n'
