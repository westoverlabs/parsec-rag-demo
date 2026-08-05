#!/usr/bin/env bash
# rehearse.sh -- push the Step 5 demo script through non-interactively.
#
# This runs the SAME ordered sequence of prompts and terminal actions that the
# README's "The Script" section tells you to perform live, but via
# `opencode run "<prompt>"` instead of a TUI session -- one call per prompt,
# printing each prompt and the answer it produced.
#
#     ./rehearse.sh                      # local llama3.2
#     ./rehearse.sh --model gpt-oss:20b-cloud
#     ./rehearse.sh --list               # print the script without running it
#
# THIS IS NOT THE DEMO. Give the talk from the real TUI (`./start_tui_demo.sh`) --
# an audience should watch a live session, not a shell script. This is the
# rehearsal/regression tool: run it before a talk to confirm the whole flow still
# behaves, without retyping nine prompts by hand.
#
# WHY SEPARATE `opencode run` CALLS WORK: every step's state lives in the
# FILESYSTEM -- the contents of astro_kg.json and whether .rag_off exists -- not
# in conversation memory. Each `opencode run` is a fresh session with no history,
# and that is fine, because the MCP server re-reads both on every single tool
# call. Step 9 proving the poisoned answer does not depend on step 8 being in the
# same conversation; it depends on the file on disk having changed.
#
# It resets the repo at the start (rehearse from a known state) and at the end
# (leave it clean for the next person).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

MODEL="${MODEL:-llama3.2}"
LIST_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --model) MODEL="${2:?--model needs a value}"; shift 2 ;;
    --list)  LIST_ONLY=1; shift ;;
    # Header comment block, stopping at the first line of real code.
    -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/,""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)" >&2; exit 1 ;;
  esac
done

BOLD=$'\033[1m'; DIM=$'\033[2m'; CYAN=$'\033[36m'; YELLOW=$'\033[33m'; OFF=$'\033[0m'

STEP=0

banner() { printf '\n%s%s%s\n' "$BOLD" "$1" "$OFF"; }

# A prompt to type into the TUI.
say_prompt() {
  STEP=$((STEP + 1))
  printf '\n%s[%02d] TYPE:%s %s%s%s\n' "$BOLD" "$STEP" "$OFF" "$CYAN" "$1" "$OFF"
}

# A thing you do in a second terminal.
say_action() {
  STEP=$((STEP + 1))
  printf '\n%s[%02d] DO:%s   %s%s%s\n' "$BOLD" "$STEP" "$OFF" "$YELLOW" "$1" "$OFF"
}

note() { printf '%s     %s%s\n' "$DIM" "$1" "$OFF"; }

run_prompt() {
  local prompt="$1"
  say_prompt "$prompt"
  [ "$LIST_ONLY" = "1" ] && return 0
  # `opencode run` is one-shot and non-interactive: fresh session, no history.
  if ! opencode run --agent astro --model "ollama/$MODEL" "$prompt" 2>&1 | sed 's/^/     /'; then
    printf '     (this step failed -- see output above)\n'
  fi
}

run_action() {
  local label="$1"; shift
  say_action "$label"
  [ "$LIST_ONLY" = "1" ] && return 0
  "$@"
}

# --------------------------------------------------------------------------

if [ "$LIST_ONLY" != "1" ]; then
  command -v opencode >/dev/null 2>&1 \
    || { echo "opencode not found. Run ./start_tui_demo.sh --check first." >&2; exit 1; }
  banner "Rehearsing the Step 5 demo script  (model: $MODEL)"
  note "Not the live demo -- this is the regression run."
else
  banner "The Step 5 demo script  (--list: nothing will be run)"
fi

# ---- Act 0: known-clean start -------------------------------------------
run_action "./reset_demo.sh   (start from a known-clean state)" ./reset_demo.sh

# ---- Act 1: grounded baseline -------------------------------------------
banner "Act 1 -- the grounded baseline"
note "Expect: mean-motion resonances with Jupiter, 3:1 at ~2.50 AU. Precise and repeatable."
run_prompt "What causes the Kirkwood gaps?"

# ---- Act 2: toggle grounding off, then back on --------------------------
banner "Act 2 -- turn grounding off, mid-conversation"
note "Nothing restarts. The MCP server re-reads the flag on every call."
run_action "touch .rag_off" touch .rag_off
note "Expect: announces UNGROUNDED, then a lottery -- often wrong, and different each time."
run_prompt "What causes the Kirkwood gaps?"
run_prompt "What causes the Kirkwood gaps?"
note "Asking twice is the point: watch the answer change."
run_action "rm .rag_off" rm -f .rag_off
note "Expect: precision and repeatability return."
run_prompt "What causes the Kirkwood gaps?"

# ---- Act 3: edit the knowledge base live --------------------------------
banner "Act 3 -- add a fact while the agent is running"
note "Expect: the new fact is retrievable on the very next question. No reindex."
note "llama3.2 lands this tool call about 3 times in 4; if it prints JSON as"
note "text instead of acting, just ask again. Cloud models are reliable here."
run_prompt "Use kg_fact to add a fact with topic 3200 Phaethon and text: 3200 Phaethon is a B-type near-Earth asteroid and the parent body of the Geminid meteor shower."
run_prompt "Tell me about the parent body of the Geminids."

# ---- Act 4: poison it ---------------------------------------------------
banner "Act 4 -- poison the knowledge base"
note "The payload of the whole demo: grounding is TRUST, not TRUTH."
note "Done from the terminal, not via a prompt: small models mangle a long"
note "verbatim string in a tool call, and a silently-failed poisoning kills"
note "the punchline. See the comment at the top of poison_kb.sh."
run_action "./poison_kb.sh" ./poison_kb.sh
note "Expect: the magnetic-field falsehood, stated with total confidence."
run_prompt "What causes the Kirkwood gaps?"

# ---- Act 5: clean up, and prove it ---------------------------------------
banner "Act 5 -- reset, and show the truth comes back"
run_action "./reset_demo.sh" ./reset_demo.sh
note "Expect: resonances again. This also proves the reset actually worked."
run_prompt "What causes the Kirkwood gaps?"

# --------------------------------------------------------------------------
if [ "$LIST_ONLY" = "1" ]; then
  banner "That's the script -- $STEP steps."
  exit 0
fi

banner "Rehearsal complete -- verifying the repo is clean"
if git rev-parse --git-dir >/dev/null 2>&1; then
  if git diff --quiet -- astro_kg.json && [ ! -e .rag_off ]; then
    printf '    astro_kg.json clean, no .rag_off. Good to go.\n\n'
  else
    printf '    WARNING: state left behind. Run ./reset_demo.sh and check git status.\n\n'
    exit 1
  fi
fi
