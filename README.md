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

Codex uses the same hook contract, configured in TOML:

1. Install Codex (`npm install -g @openai/codex`) if needed.
2. Open your Codex config at `~/.codex/config.toml` (create it if it doesn't
   exist) and add the block from [`codex-config.example.toml`](./codex-config.example.toml):
   ```toml
   [[hooks.UserPromptSubmit]]

   [[hooks.UserPromptSubmit.hooks]]
   type = "command"
   command = 'python3 "$(git rev-parse --show-toplevel)/ground_with_kg.py"'
   timeout = 10
   ```
3. Run `codex` from inside your clone of this repo (so `git rev-parse` finds the
   script) and ask an astronomy question. Same grounding, same script.

> **Why the same script works in both:** Codex uses the same `UserPromptSubmit`
> hook event schema as Claude Code, including the `hookSpecificOutput.additionalContext`
> output field. See the Codex config & hooks reference:
> <https://developers.openai.com/codex/config-reference>. Codex is evolving
> quickly — if the block ever silently does nothing, check the current Codex hooks
> docs for renamed fields; the retrieval logic in `ground_with_kg.py` is unaffected.

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
| `.claude/settings.json` | Ready-made Claude Code hook config (works on clone). |
| `codex-config.example.toml` | The equivalent Codex config block to paste into `~/.codex/config.toml`. |

## Requirements

Python 3.9+ standard library. That's the entire dependency list.

## License

MIT — see [`LICENSE`](./LICENSE). Built by Westover Labs for the LSST / Rubin
astronomer talk. Share it, fork it, point it at your own data.
