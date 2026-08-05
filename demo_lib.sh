#!/usr/bin/env bash
# demo_lib.sh -- shared helpers for the PARSEC demo scripts. Sourced, not run.
#
# Sourced by start_tui_demo.sh and reset_demo.sh so the two share ONE copy of
# the session-clearing logic and can never drift apart. The sourcing script must
# already have set REPO_DIR and defined info().

# Clear this repo's opencode TUI session history -- and ONLY this repo's.
#
# WHY: the interactive Step-5 TUI keeps one running conversation. This demo asks
# the SAME question several times as grounding flips on -> off -> poisoned; with
# a stale transcript in context a small model replays its previous answer ("I
# already answered this") instead of re-reading the knowledge base. One-shot
# `opencode run` never hits this -- each run is a fresh session -- but the live
# TUI does, so we wipe the slate between runs.
#
# SAFETY: we delete only sessions whose project directory is THIS repo (matched
# against REPO_DIR). Your opencode work in every other project is untouched.
clear_opencode_sessions() {
  local note="${1:-}"
  command -v opencode >/dev/null 2>&1 || { info "opencode      not installed -- no sessions to clear."; return 0; }
  command -v python3  >/dev/null 2>&1 || { info "opencode      python3 missing -- skipping session clear."; return 0; }

  # Fail closed: without a concrete repo path we would match everything, so bail.
  if [ -z "${REPO_DIR:-}" ] || [ "$REPO_DIR" = "/" ]; then
    info "opencode      REPO_DIR unset -- refusing to clear sessions (fail-safe)."
    return 0
  fi

  # The repo path is passed to python as an ARGUMENT, not via env: an env
  # assignment on the left of a pipe applies only to the left command, so it
  # would never reach python here -- and an empty match string would delete
  # every session on the machine. argv is the only reliable channel.
  local ids
  ids=$(opencode session list --format json -n 999 2>/dev/null | python3 -c '
import sys, json
repo = (sys.argv[1] if len(sys.argv) > 1 else "").rstrip("/")
if not repo:            # never match on an empty path
    sys.exit(0)
prefix = repo + "/"
try:
    data = json.load(sys.stdin)
except Exception:
    data = []
for s in data:
    d = (s.get("directory") or "").rstrip("/")
    if s.get("id") and (d == repo or d.startswith(prefix)):
        print(s["id"])
' "$REPO_DIR" 2>/dev/null) || ids=""

  if [ -z "${ids:-}" ]; then
    info "opencode      no session history for this repo${note:+ ($note)}."
    return 0
  fi

  local n=0 id
  while IFS= read -r id; do
    [ -n "$id" ] || continue
    if opencode session delete "$id" >/dev/null 2>&1; then
      n=$((n + 1))
    fi
  done <<< "$ids"
  info "opencode      cleared $n TUI session(s) for this repo${note:+ ($note)}."
}
