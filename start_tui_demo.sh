#!/usr/bin/env bash
# start_tui_demo.sh -- from nothing to an interactive, grounded, live-editable
# astronomy agent, on your laptop or on Ollama's free cloud tier.
#
#     ./start_tui_demo.sh                 # local model (default)
#     ./start_tui_demo.sh --cloud         # Ollama Cloud instead of local compute
#     ./start_tui_demo.sh --check         # set up and verify, but don't launch
#     MODEL=qwen3.5:2b ./start_tui_demo.sh
#
# It installs only what's missing, and never installs anything without telling
# you first.
#
# TWO WAYS TO GET A MODEL:
#   (a) LOCAL  -- llama3.2 (~2 GB) runs on your machine. Nothing leaves it, and
#                 it works with no account and no network once pulled.
#   (b) CLOUD  -- if your laptop is too slow, `ollama signin` connects you to
#                 Ollama Cloud's free tier. Same commands, same API, same demo;
#                 the compute just happens elsewhere.
# Either way OpenCode and the MCP grounding server are wired up identically.

set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_ONLY=0
USE_CLOUD=0

# A "low usage" cloud model -- gentler on the free tier's hourly/daily allowance
# than the very large ones.
CLOUD_MODEL="${CLOUD_MODEL:-gpt-oss:20b-cloud}"

for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --cloud) USE_CLOUD=1 ;;
    # Header comment block, stopping at the first line of real code.
    -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/,""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 1 ;;
  esac
done

if [ "$USE_CLOUD" = "1" ]; then
  MODEL="${MODEL:-$CLOUD_MODEL}"
else
  MODEL="${MODEL:-llama3.2}"
fi

say()  { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
info() { printf '    %s\n' "$1"; }
die()  { printf '\n\033[31mx  %s\033[0m\n' "$1" >&2; exit 1; }

cd "$REPO_DIR"

# ---------------------------------------------------------------- 1. Ollama
say "Checking Ollama (runs the model on your machine)"
if command -v ollama >/dev/null 2>&1; then
  info "ollama found: $(command -v ollama)"
else
  info "ollama not found."
  case "$(uname -s)" in
    Darwin)
      if command -v brew >/dev/null 2>&1; then
        info "installing with: brew install ollama"
        brew install ollama
      else
        die "Install Ollama from https://ollama.com then re-run this script."
      fi
      ;;
    Linux)
      info "installing with the official script from https://ollama.com"
      curl -fsSL https://ollama.com/install.sh | sh
      ;;
    *)
      die "Install Ollama from https://ollama.com then re-run this script."
      ;;
  esac
fi

# ------------------------------------------------------- 2. Ollama server up
say "Checking the Ollama server at $OLLAMA_HOST"
if curl -sf "$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then
  info "server is up."
else
  info "not responding; starting 'ollama serve' in the background..."
  ollama serve >/tmp/ollama-serve.log 2>&1 &
  for _ in $(seq 1 30); do
    sleep 1
    curl -sf "$OLLAMA_HOST/api/tags" >/dev/null 2>&1 && break
  done
  curl -sf "$OLLAMA_HOST/api/tags" >/dev/null 2>&1 \
    || die "Ollama did not come up. See /tmp/ollama-serve.log"
  info "server is up."
fi

# ------------------------------------------------------------- 3. The model
cloud_signin() {
  cat <<'EOF'
    Ollama Cloud runs the model on Ollama's machines instead of yours.
    There is a free tier, and this demo is light enough to sit inside it.

    `ollama signin` will open a BROWSER TAB. Sign up or log in there
    (creating the account needs a real email, so it has to be you, not
    this script), then come back to this terminal.
EOF
  printf '\n'
  read -r -p "    Press Enter to open the sign-in page (or Ctrl-C to abort)... " _ || true
  ollama signin || die "Sign-in did not complete. Re-run: ollama signin"
}

offer_cloud_fallback() {
  # Only ask if a human is actually watching.
  [ -t 0 ] || return 1
  printf '\n'
  read -r -p "    Use Ollama Cloud's free tier instead? [y/N] " reply || return 1
  case "$reply" in
    [yY]*) return 0 ;;
    *) return 1 ;;
  esac
}

if [ "$USE_CLOUD" = "1" ]; then
  say "Using Ollama Cloud: $MODEL"
  info "checking whether this machine can already reach cloud models..."
  if ollama run "$MODEL" "reply with OK only" >/dev/null 2>&1; then
    info "cloud models are reachable -- you're signed in."
  else
    info "not signed in yet."
    cloud_signin
    ollama run "$MODEL" "reply with OK only" >/dev/null 2>&1 \
      || die "Still cannot reach $MODEL. Check https://ollama.com/settings and try: ollama signin"
    info "cloud model reachable."
  fi
else
  say "Checking the model: $MODEL"
  if curl -sf "$OLLAMA_HOST/api/tags" | grep -q "\"${MODEL}\(:latest\)\?\""; then
    info "$MODEL is already pulled."
  else
    info "pulling $MODEL (about 2 GB for llama3.2 -- one time only)..."
    if ollama pull "$MODEL"; then
      info "pulled $MODEL."
    else
      info "the pull failed -- no disk space, no network, or the machine is struggling."
      if offer_cloud_fallback; then
        USE_CLOUD=1
        MODEL="$CLOUD_MODEL"
        cloud_signin
        ollama run "$MODEL" "reply with OK only" >/dev/null 2>&1 \
          || die "Could not reach $MODEL after sign-in."
        info "using cloud model $MODEL."
      else
        die "Could not get a model. Re-run with --cloud to use Ollama Cloud."
      fi
    fi
  fi
fi

# ----------------------------------------------------------------- 4. Python
say "Checking Python"
command -v python3 >/dev/null 2>&1 || die "python3 not found. Install Python 3.9+."
info "$(python3 --version)"

# ---------------------------------------------------------------- 5. opencode
say "Checking opencode (the TUI agent)"
if command -v opencode >/dev/null 2>&1; then
  info "opencode found: $(opencode --version 2>/dev/null || echo present)"
else
  if ! command -v npm >/dev/null 2>&1; then
    info "npm not found (needed to install opencode)."
    case "$(uname -s)" in
      Darwin)
        if command -v brew >/dev/null 2>&1; then
          info "installing Node with: brew install node"
          brew install node
        else
          die "Install Homebrew (https://brew.sh) then: brew install node -- or install Node.js from https://nodejs.org, then re-run."
        fi
        ;;
      Linux)
        if command -v apt-get >/dev/null 2>&1; then
          info "installing with: sudo apt-get install -y nodejs npm"
          sudo apt-get update && sudo apt-get install -y nodejs npm
        elif command -v dnf >/dev/null 2>&1; then
          info "installing with: sudo dnf install -y nodejs npm"
          sudo dnf install -y nodejs npm
        elif command -v pacman >/dev/null 2>&1; then
          info "installing with: sudo pacman -S --noconfirm nodejs npm"
          sudo pacman -S --noconfirm nodejs npm
        else
          die "Install Node.js with your distro's package manager (nodejs + npm), then re-run."
        fi
        ;;
      *)
        die "Install Node.js from https://nodejs.org, then re-run. (Windows isn't a supported path for this demo.)"
        ;;
    esac
  fi
  command -v npm >/dev/null 2>&1 || die "npm still not found after install attempt -- install Node.js manually, then re-run."
  info "installing with: npm install -g opencode-ai"
  npm install -g opencode-ai
fi

# ------------------------------------------- 6. MCP server + grounding state
say "Checking the local MCP server (astro_mcp.py)"
[ -f "$REPO_DIR/astro_mcp.py" ] || die "astro_mcp.py missing -- are you in the repo?"
[ -f "$REPO_DIR/opencode.json" ] || die "opencode.json missing -- are you in the repo?"

# opencode.json in this repo already registers the server and the Ollama
# provider, so there is nothing to write into your global config.
if python3 astro_mcp.py --selftest >/dev/null 2>&1; then
  info "MCP server self-test passed."
else
  # --selftest is optional; fall back to a plain import check.
  python3 -c "import astro_mcp" 2>/dev/null \
    && info "MCP server imports cleanly." \
    || die "astro_mcp.py failed to load. Run: python3 astro_mcp.py"
fi

rm -f "$REPO_DIR/.rag_off"
info "grounding flag reset: grounding is ON (.rag_off absent)."

if command -v opencode >/dev/null 2>&1; then
  say "Verifying opencode can see the MCP server"
  opencode mcp list 2>&1 | sed 's/^/    /' || info "(could not list; the TUI will still try)"
fi

# ------------------------------------------------------------------ 7. Launch
if [ "$CHECK_ONLY" = "1" ]; then
  say "All set (--check: not launching)"
  info "Start it yourself with:  opencode --agent astro --model ollama/$MODEL"
  exit 0
fi

WHERE="local, via Ollama"
[ "$USE_CLOUD" = "1" ] && WHERE="Ollama Cloud, free tier"

# The greeting Claude Code and Codex get from session_greeting.py has to be
# printed here instead. OpenCode has no config-declared hooks; it does have a
# plugin API, but its session.created event does not fire until the user submits
# a first message -- too late to greet anyone -- and neither console.log (which
# corrupts the TUI) nor tui.showToast() (which never rendered) can put text on
# screen beforehand. Tested; see the README. Not the model speaking first, but
# the same orientation at the same moment, which is what matters to a newcomer.
say "Welcome to the PARSEC RAG demo"
cat <<'EOF'
    You are about to drop into a conversation with a small AI model running
    entirely on this machine. No API key, no cloud account.

    If you have not used one of these before: this is a running conversation,
    not a one-shot command. Type a question, press Enter, and keep going --
    context carries between messages. The answer streams in a piece at a time,
    and you will sometimes see a tool call appear mid-answer. That is the
    knowledge base being consulted. It is the demo working, not an error.

    Ctrl-C, or /exit, to leave.
EOF

say "Launching the interactive agent"
cat <<EOF
    Model:    $MODEL  ($WHERE)
    Agent:    astro   (grounded by astro_kg.json through MCP)

    The script (full version + narration in the README, "The Script"):
      1.  ASK   What causes the Kirkwood gaps?
      2.  DO    touch .rag_off        (in a second terminal)
      3.  ASK   the same question, twice -- watch it wander
      4.  DO    rm .rag_off
      5.  ASK   again -- precision returns
      6.  ASK   Use kg_fact to add a fact with topic 3200 Phaethon and text: ...
      7.  DO    ./poison_kb.sh        (the payload)
      8.  ASK   What causes the Kirkwood gaps?   -- now it lies, confidently
      9.  DO    ./reset_demo.sh       (always, before handing this on)

    Rehearse the whole thing non-interactively:  ./rehearse.sh
    Print it as a cue card:                      ./rehearse.sh --list

    Ctrl-C or /exit to quit.
EOF

if [ "$USE_CLOUD" != "1" ] && [ "$MODEL" = "llama3.2" ]; then
  cat <<'EOF'
    NOTE: llama3.2 is fast but flaky at TOOL CALLS -- roughly one prompt in four
    it prints a blob of JSON instead of actually calling the tool. Just ask
    again. For a steadier room, re-run with:  ./start_tui_demo.sh --cloud
EOF
fi
# OpenCode's TUI takes over and CLEARS the screen, so everything printed above --
# including the welcome -- vanishes the instant it starts. Wait for the user
# rather than sleeping, so the greeting is actually read. (A bare sleep looked
# fine in testing and then wiped the banner in under a second on a real launch.)
if [ -t 0 ]; then
  printf '\n'
  read -r -p "    Press Enter to start the session (the screen will clear)... " _ || true
else
  sleep 2
fi

# Pass the model explicitly: the `astro` agent in opencode.json pins a default,
# and MODEL= / --cloud must be able to override it.
exec opencode --agent astro --model "ollama/$MODEL"
