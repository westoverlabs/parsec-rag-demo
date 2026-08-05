#!/usr/bin/env bash
# reset_demo.sh -- put the repo back the way it was before the demo.
#
# The Step 5 demo deliberately makes a mess: it edits astro_kg.json (adding
# facts, and poisoning the Kirkwood gaps fact with unphysical nonsense) and
# leaves a .rag_off flag behind if you toggled grounding off. Run this between
# demo runs, before handing the laptop to the next person, or any time you're
# not sure what state the knowledge base is in.
#
#     ./reset_demo.sh
#
# Safe to run at any time, including when nothing is dirty. It touches ONLY the
# demo's own state -- astro_kg.json, the .rag_off flag, and any stray atomic-write
# temp files. It will never discard edits to anything else you were working on.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

say()  { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
info() { printf '    %s\n' "$1"; }

say "Resetting the demo"

# ---------------------------------------------------------- knowledge base
if git rev-parse --git-dir >/dev/null 2>&1; then
  if git diff --quiet -- astro_kg.json 2>/dev/null; then
    info "astro_kg.json  already matches the committed version -- nothing to undo."
  else
    # Scoped to the one file on purpose: never `git checkout .`, never a reset.
    git checkout -- astro_kg.json
    info "astro_kg.json  restored from git (poisoned and added facts discarded)."
  fi
else
  info "astro_kg.json  NOT restored -- this isn't a git checkout."
  info "               (Downloaded as a zip? Re-download to get a clean KB.)"
fi

# ------------------------------------------------------------ grounding flag
if [ -e .rag_off ]; then
  rm -f .rag_off
  info ".rag_off       removed -- grounding is back ON."
else
  info ".rag_off       absent -- grounding was already ON."
fi

# ------------------------------------------------- stray atomic-write temps
# The MCP server writes to a temp file then renames. A crash mid-write could
# leave one behind; they're gitignored, so sweep them rather than let them rot.
temps=$(find . -maxdepth 1 -name '.astro_kg.*.tmp' 2>/dev/null || true)
if [ -n "$temps" ]; then
  # shellcheck disable=SC2086
  rm -f $temps
  info "temp files     cleaned up."
else
  info "temp files     none left behind."
fi

# ------------------------------------------------------------------ verify
say "State after reset"
fact_count=$(python3 -c "import json;print(len(json.load(open('astro_kg.json'))['facts']))" 2>/dev/null || echo "?")
info "facts in the knowledge base: $fact_count"
info "grounding: ON"

if git rev-parse --git-dir >/dev/null 2>&1; then
  if git diff --quiet -- astro_kg.json 2>/dev/null; then
    info "astro_kg.json is clean."
  else
    info "WARNING: astro_kg.json still differs from git -- check 'git status'."
  fi
fi

printf '\n    Ready for the next run.\n\n'
