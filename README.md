# RAG + Knowledge Graph in ~90 lines — an astronomy demo

*A hands-on companion to the LSST / Rubin AI talk. You already have the pieces.*

This is a tiny, self-contained demo that grounds an AI coding assistant (Claude
Code or OpenAI Codex) in **your own astronomy facts** — automatically, every time
you ask a question. No database, no embeddings library, no API keys, no network.
Just Python's standard library and a JSON file you can read and edit.

---

## The idea in two lines

- **RAG** (Retrieval-Augmented Generation) = before the model answers, fetch the
  relevant facts and hand them over, so it reasons from *your* knowledge instead
  of its fuzzy memory.
- **A hook** is a small program the assistant runs *for you* on every prompt. Put
  RAG in the hook and grounding becomes invisible: you ask, the right facts appear,
  you focus on the science — not on managing context.

The "knowledge graph" here is a small [`astro_kg.json`](./astro_kg.json) of
asteroid-family, orbital-element, and LSST survey facts. Swap in your own and the
demo grounds the model in whatever domain you care about.

---

## See it in 10 seconds (no setup)

You need Python 3.9+ (check with `python3 --version`). Then:

```bash
git clone https://github.com/neherdata/lsst-hook-rag-demo.git
cd lsst-hook-rag-demo
python3 demo.py "Why do we use proper elements to find asteroid families?"
```

You'll see two panels — what the model sees **without** the hook (your bare
question) and **with** it (your question plus the exact facts the hook retrieved).
That injected block is precisely what gets fed to Claude Code or Codex once you
wire the hook in below.

Try a few:

```bash
python3 demo.py "What is the Vesta family and where do the HED meteorites come from?"
python3 demo.py "How many asteroids will LSST discover, and how big is the alert stream?"
python3 demo.py "How do you link single-night detections into an orbit?"
python3 demo.py "recommend a good pizza recipe"   # off-topic -> injects nothing
```

---

## What actually happens (the whole trick)

`ground_with_kg.py` is a **UserPromptSubmit hook**. Claude Code and Codex both run
it right before your prompt reaches the model, and both hand it a JSON object on
standard input. The script:

1. **reads** your prompt from stdin,
2. **searches** `astro_kg.json` — plain keyword overlap, most-relevant first,
3. **selects** the top few facts,
4. **injects** them back by printing this JSON:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "[grounding facts ...] - Osculating vs proper elements: ..."
  }
}
```

That `additionalContext` field is understood by **both** Claude Code and Codex, so
**one script works in both tools unchanged** — only the config file differs. If
anything goes wrong the hook injects nothing and exits cleanly, so it can never
block your prompt.

---

## Wire it into Claude Code

This repo already ships [`.claude/settings.json`](./.claude/settings.json) with the
hook configured, so it's automatic:

1. Install Claude Code (`npm install -g @anthropic-ai/claude-code`) if you don't
   have it.
2. From inside your clone of this repo, start it:
   ```bash
   cd lsst-hook-rag-demo
   claude
   ```
   Claude Code reads `.claude/settings.json` and registers the hook. (It may ask
   you once to approve the project's hook — say yes.)
3. Ask an astronomy question, e.g. *"Which spectral class dominates the Eos
   family?"* The hook grounds it silently. Type `/hooks` to confirm a
   `UserPromptSubmit` hook is active.

To use it in **any** project, copy the `hooks` block from `.claude/settings.json`
into your own `~/.claude/settings.json` and point the command at wherever you put
`ground_with_kg.py` and `astro_kg.json`.

---

## Wire it into Codex

This repo already ships [`.codex/hooks.json`](./.codex/hooks.json) — the Codex
counterpart of `.claude/settings.json`, registering the **same** `ground_with_kg.py`
under the **same** `UserPromptSubmit` event. So Codex needs no config editing — just a
one-time trust approval:

1. Install Codex (`npm install -g @openai/codex`), version **0.146 or newer**
   (`codex --version`).
2. From inside your clone, run Codex once:
   ```bash
   cd lsst-hook-rag-demo
   codex
   ```
   Codex discovers `.codex/hooks.json` by working directory and asks you to
   **trust the grounding hook** — Codex won't silently run a program a cloned repo
   dropped into your project (a good default for code you didn't write). Approve it
   once; Codex records the trust and the hook fires on every prompt afterward, in
   both interactive Codex *and* headless `codex exec`.
3. Ask an astronomy question — the hook grounds it silently, exactly as in Claude Code.

> **Same script, two tiny registration files.** `ground_with_kg.py` is byte-for-byte
> identical in both tools — the ~90 lines never change. Only the small registration
> file differs, and even those are near-identical JSON with the same `UserPromptSubmit`
> event and the same `hookSpecificOutput.additionalContext` output. The only
> differences: how each names the repo root in the command
> (`$CLAUDE_PROJECT_DIR` for Claude Code vs `$(git rev-parse --show-toplevel)` for
> Codex), and that Codex's entry takes an optional `timeout`. That's the whole delta.

> **Heads-up if you script `codex exec` directly:** an **untrusted** hook is silently
> skipped in headless `exec` (no error, it just doesn't run). Do the one-time interactive
> `codex` trust above first, or pass `--dangerously-bypass-hook-trust` on each run.
> Codex is evolving quickly — if grounding ever stops appearing, re-run `codex`
> interactively to re-approve the hook; the retrieval logic in `ground_with_kg.py`
> is unaffected.

---

## Ask a local Ollama model (free, laptop-portable)

Want to see RAG grounding in action on a **real model** without any cloud service or API key?
This demo ships `ask_ollama.py`, which runs the same retrieval + grounding on a local
**Ollama** instance so you can watch the before-and-after answers side by side.

This is especially powerful for small models (like **llama3.2** or **qwen3.5:2b** at ~2GB)
because their built-in recall is the thinnest — RAG grounding closes the widest gap on
exactly the models attendees will run on their laptops tonight. The ungrounded version
flounders; grounded, it nails it.

### Setup (5 minutes)

1. **Install Ollama** (https://ollama.com) if you don't have it, then start the server:
   ```bash
   ollama serve
   ```
   (Runs on `localhost:11434` by default; set `OLLAMA_HOST=http://your.host:11434` if elsewhere.)

2. **Pull a small model** (run in another terminal):
   ```bash
   ollama pull llama3.2   # ~2 GB; very capable for its size
   ```
   Or use any model already on your system — `qwen3.5:2b` (~2.7 GB), `gemma4:7b`, etc.

3. **Run the grounded question**:
   ```bash
   python3 ask_ollama.py "Why do we use proper elements to find asteroid families?"
   ```

   The script calls Ollama **twice** — once without grounding, once with your KG facts
   injected — and prints both answers. You'll see the difference immediately: the
   grounded model gives a crisper, more accurate answer.

### Options

```bash
# Use a different model
OLLAMA_MODEL=qwen3.5:2b python3 ask_ollama.py "..."

# Skip the ungrounded call (faster if you just want to see the grounded answer)
python3 ask_ollama.py --grounded-only "..."

# Point at a different Ollama host (e.g., on a server)
OLLAMA_HOST=http://192.168.1.100:11434 python3 ask_ollama.py "..."
```

### Why RAG matters MORE for small models

Large cloud models (Claude, GPT) have enormous recall built in — they've seen vast
swaths of the internet and remember a lot. RAG helps them stay grounded in YOUR specific
facts, but they often do okay without it.

Small local models have thin recall — they only "know" what they were trained on, and
details are fuzzy. **RAG grounding is what turns them from "maybe right" to "definitely
right."** That's why tonight's demo lands hardest on the laptop models attendees are
actually running.

---

## Before / after — why it matters

**Without the hook**, you ask *"Why do we cluster in proper element space to find
families?"* and the model answers from memory — usually fine, sometimes subtly
wrong, and it can't know facts specific to *your* catalog.

**With the hook**, the model first receives your verified statement — *"Asteroid
families are identified by clustering in PROPER element space, not osculating
elements, because proper elements are nearly invariant over millions of years"* —
and answers from that. You never typed it. You never pasted it. The plumbing did
it for you.

That is the payload of the talk: **RAG over a knowledge graph is about 90 lines of
standard-library Python in a hook.** Point it at your asteroid families, your
observing logs, your instrument notes — and spend your attention on the science
(*"could these two detections be the same object?"*) instead of on managing arrays
of context by hand.

---

## Using this with OpenCode (TUI agent)

If you use **OpenCode** or **Goose** (a TUI AI agent), you can wire in grounding via
environment variables and context injection. The exact setup depends on which tool you
use and how its extension system works.

**Best approach for tonight's talk:** use `ask_ollama.py` (above) to see the grounding
effect live on a real model, then run OpenCode/Goose pointed at the same local Ollama
instance. They'll use the same model and backend — you've already proven the power of
RAG with the side-by-side demo.

### If using Goose (CLI agent)

Goose supports context injection via the "Top Of Mind" (`tom`) extension:

```bash
# Set up context before each session:
export GOOSE_MOIM_MESSAGE_FILE=$(pwd)/astro_kg.json
goose session --name astronomy-demo
```

Or point to a formatted context file:

```bash
export GOOSE_MOIM_MESSAGE_TEXT="You have access to astronomy facts. Use them to ground your answers."
goose session
```

**To use Ollama**: Goose supports local-models via `goose local-models`, and can be
configured to use local inference. Check `~/.config/goose/config.yaml` for provider
settings; the environment variable `GOOSE_PROVIDER` controls which model backend is used.

### If using other editors / TUI agents

If your TUI agent has a hook or context-injection system, follow this pattern:

1. Point the hook at `ground_with_kg.py` (like Claude Code / Codex do above).
2. Or: inject the `astro_kg.json` facts into your agent's system context via that tool's
   config or environment.
3. Or: use `ask_ollama.py` first to demonstrate the effect, then continue your session
   knowing grounding is in play.

The retrieval logic in `ground_with_kg.py` is tool-agnostic — it works anywhere you can
call Python and inject JSON. The ~90 lines are the portable part; the hook registration
varies by tool.

---

## Make it yours

Open [`astro_kg.json`](./astro_kg.json) and add a fact:

```json
{
  "topic": "My favorite object",
  "keywords": ["phaethon", "geminids", "meteor", "shower", "b-type"],
  "text": "3200 Phaethon is a B-type near-Earth asteroid and the parent body of the Geminid meteor shower; it shows comet-like activity near perihelion."
}
```

Re-run `python3 demo.py "tell me about the Geminids parent body"` and it's there.
That's the whole editing workflow — no schema, no migration, no rebuild.

---

## Files

| File | What it is |
|------|-----------|
| `ground_with_kg.py` | The hook — reads the prompt, retrieves facts, injects them. ~90 lines, stdlib only. |
| `astro_kg.json` | The knowledge base — asteroid families, orbital elements, LSST facts. Edit freely. |
| `demo.py` | Before/after viewer so you can see the effect without wiring anything up. |
| `ask_ollama.py` | **Free laptop path** — ask a local Ollama model twice (ungrounded vs grounded). See RAG in action, no API key. |
| `.claude/settings.json` | Ready-made Claude Code hook registration (works on clone). |
| `.codex/hooks.json` | Ready-made Codex hook registration (works on clone, after a one-time trust approval). |

## Requirements

Python 3.9+ standard library. That's the entire dependency list.

## License

MIT — see [`LICENSE`](./LICENSE). Built by Westover Labs for the LSST / Rubin
astronomer talk. Share it, fork it, point it at your own data.
