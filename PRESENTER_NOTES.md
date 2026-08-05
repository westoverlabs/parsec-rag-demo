# Presenter notes — read before you demo, keep off the projector

These are the caveats, measured findings, and "why we built it this way" that the
README deliberately leaves out so the walkthrough stays clean for the room. This
file is for **you**, not the audience.

---

## Reliability: what actually flakes, and what to do

- **Run Step 4 (the opencode agent) with `--cloud` in front of a room.** `llama3.2`
  is fast but misses a tool call roughly one prompt in five — it prints the tool-call
  JSON as plain text and nothing happens. Harmless (just ask again), but
  `./start_tui_demo.sh --cloud` (`gpt-oss:20b-cloud`, still free) is materially
  steadier. Measured on this host:

  | Model | Simple question | Add-a-fact prompt |
  |---|---|---|
  | `llama3.2` (local) | 5/6 | 3/4 |
  | `gpt-oss:20b-cloud` | 6/6 | reliable in all runs |

  This only affects the Step 4 agent loop. **Step 1's `demo.py` makes no tool calls
  and is rock-solid on `llama3.2`.**

- **Act 4 (poison) is a script, not a prompt, on purpose.** Asking the agent to
  *edit* the Kirkwood fact with a long verbatim sentence fails silently on
  `llama3.2` — one run truncated at the apostrophe in "Jupiter's" (leaving the KB
  vaguely true, punchline gone), another emitted malformed JSON and did nothing.
  `poison_kb.sh` makes the most important beat deterministic — and it's better
  theatre: the room watches *you* change the source of truth. On `gpt-oss:20b-cloud`
  the prompt-driven edit does work if you'd rather show that.

- **Reasoning models pause.** `qwen3.5:2b` thinks before answering — silent gap.
  `llama3.2` is the snappier choice for a live room.

- **The `astro` agent has file/shell/edit tools disabled** — it can only touch the
  knowledge base. Added after `llama3.2`, mid-run, tried to edit a file outside the
  repo. Don't remove that in front of an audience.

## Retrieval: honest about the index

Retrieval is **TF-IDF cosine similarity** now (pure stdlib — `math` + `collections`,
no numpy, no embeddings library), an upgrade from the original keyword-overlap. It's
still ~120 lines you can read, and it's still not magic:

- It's term-frequency similarity, not semantics — a query has to share *words* with
  a fact, just weighted by how discriminative each word is. TF-IDF fixed the worst
  phrasing misses (e.g. "gaps in the asteroid belt" now decisively finds the
  Kirkwood fact; "Kirkwood gaps in the main belt" no longer drags in unrelated family
  facts), but a query in genuinely different vocabulary can still miss. Phrase demo
  questions in the KB's own words, or upgrade to embeddings — that's the natural next
  step, and a great "fork this and improve it" contribution.
- **The model still chooses whether to call the tool** in the opencode path. Usually
  it does; a small model occasionally answers without it. The hook path (Claude
  Code / Codex, Step 5) has no such gap — grounding there is automatic.

## Why the opencode plugin story is what it is

opencode has **no config-declared hooks** like `.claude/settings.json` /
`.codex/hooks.json` — it has a code-based plugin API (`.opencode/plugin/`). We chose
the **MCP tool** (`astro_mcp.py`) for grounding instead of a plugin, deliberately:

- A `session.created` plugin can't greet *before* input — the session isn't created
  until the first prompt is sent (measured: ~29 s after plugin init, at first
  keystroke). `console.log` from a plugin corrupts the TUI (stdout is the render
  channel). `tui.showToast()` returned success but never rendered (1.18.13). So the
  pre-input greeting comes from a **terminal banner in `start_tui_demo.sh`**, not a
  plugin.
- A `chat.message` plugin *can* silently inject grounding — but it double-grounds
  (model gets the facts *and* still calls the tool) and, worse, hides the visible
  `⚙ astro-kg_search_astro_kb {…}` tool call that is the whole point of the opencode
  path being *observable* on a projector. Silent injection would make the demo worse.

> An experimental greeting plugin lives on the `feat/opencode-plugin` branch — treat
> it as unverified until it's been watched running in a real opencode session; the
> shipped, working greeting is the terminal banner.

## Why the rehearsal runner is separate from the demo

`rehearse.sh` pushes the whole script through `opencode run` non-interactively — a
regression check, **not** the demo. Give the talk from the real TUI; an audience
should watch a live session, not a shell script scroll past. It works because every
step's state lives in the **filesystem** (`astro_kg.json` contents + whether
`.rag_off` exists), not conversation memory — each `opencode run` is a fresh session
and the MCP server re-reads both on every call. Verified, not assumed.
