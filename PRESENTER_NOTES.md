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

---

## The stage script (moved out of the README)

### The Script

Stage directions for the live demo. **TYPE** = paste into the TUI. **DO** = run in
a second terminal you keep on screen, so the audience sees the cause. Roughly six
minutes at a talking pace.

> **Before a room, consider running with `--cloud`.** `llama3.2` is fast but
> misses a tool call roughly one prompt in five, printing JSON instead of acting.
> It's harmless — ask again — but `./start_tui_demo.sh --cloud` is steadier and
> still free. Measured numbers are in 5d.

Everything below is explained in detail in 5a–5c; this section is the part you
actually perform.

> **Act 0 — start clean**
>
> 1. **DO** — `./reset_demo.sh`

> **Act 1 — the grounded baseline**
>
> 2. **TYPE** — `What causes the Kirkwood gaps?`
>
> *Expect: mean-motion resonances with Jupiter, the 3:1 at ~2.50 AU. Precise, and
> the same every time you ask.*

> **Act 2 — turn grounding off, mid-conversation**
>
> 3. **DO** — `touch .rag_off`
> 4. **TYPE** — `What causes the Kirkwood gaps?`
> 5. **TYPE** — `What causes the Kirkwood gaps?`  *(yes, ask it twice)*
> 6. **DO** — `rm .rag_off`
> 7. **TYPE** — `What causes the Kirkwood gaps?`
>
> *Nothing restarted. Steps 4 and 5 are a lottery — often wrong, and usually
> wrong in a **different way** each time. Asking twice is the point. Step 7 brings
> the precision back.*

> **Act 3 — edit the knowledge base while it's running**
>
> 8. **TYPE** — `Use kg_fact to add a fact with topic 3200 Phaethon and text: 3200 Phaethon is a B-type near-Earth asteroid and the parent body of the Geminid meteor shower.`
> 9. **TYPE** — `Tell me about the parent body of the Geminids.`
>
> *The new fact is retrievable on the very next question. No reindex, no restart.*
>
> *`llama3.2` lands this tool call about **3 times in 4** (measured). If it prints
> a blob of JSON instead of acting, it didn't really call the tool — just ask
> again. Cloud models don't have this problem.*

> **Act 4 — poison it (the payload)**
>
> 10. **DO** — `./poison_kb.sh`
> 11. **TYPE** — `What causes the Kirkwood gaps?`
>
> *Unphysical nonsense, repeated with total confidence — in the same calm register
> as the true answer. This is the moment the talk is for. See 5c.*
>
> *`poison_kb.sh` swaps the true Kirkwood fact for the magnetic-field falsehood and
> prints the before/after. It's a terminal action rather than a prompt on purpose:
> see the note below.*

> **Act 5 — reset, and show the truth comes back**
>
> 12. **DO** — `./reset_demo.sh`
> 13. **TYPE** — `What causes the Kirkwood gaps?`
>
> *Resonances again — which also proves the reset did its job.*

**Always run `./reset_demo.sh` before handing the laptop on.** It restores
`astro_kg.json` from git (scoped to that one file), clears `.rag_off`, and prints
what it changed. It's safe to run when nothing is dirty.

> **Why Act 4 is a script and Act 3 is a prompt.** Step 8 asks the agent to *add* a
> fact and that works reliably. Asking it to *edit* the Kirkwood fact with a long
> verbatim sentence does not: testing `llama3.2` on exactly that prompt, one run
> truncated the text at the apostrophe in "Jupiter's" (leaving the KB saying
> *"swept clear by Jupiter"* — vague, not false, punchline gone) and the next
> emitted malformed JSON so no edit happened at all. Both failures are silent.
> `poison_kb.sh` makes the most important beat of the demo deterministic. It's
> also better theatre: the room watches *you* change the source of truth, then
> watches the model believe you. On a stronger model (`gpt-oss:20b-cloud`) the
> prompt-driven edit does work, if you'd rather show that.

### The short version, colour-coded, for the stage

If you'd rather drive the argument from one script than type into a TUI — or you
have five minutes rather than fifteen — `stage_script.sh` runs the four beats that
carry the whole point, each behind its own coloured banner so the room can see
which beat they're in:

```bash
./stage_script.sh
```

| Beat | Colour | What happens |
|---|---|---|
| 1 — Grounded, true | green | Two real questions, answered from the knowledge base |
| 2 — Poisoning the source of truth | yellow | `poison_kb.sh` swaps one true fact for a plausible lie |
| 3 — Same question, poisoned KB | red | It repeats the lie, confidently |
| 4 — Reset | blue | `reset_demo.sh`, then ask again — the truth returns |

It pauses before each beat so you can talk over it; press Enter to fire the next
one. `--no-pause` runs it straight through, which doubles as an end-to-end check.
Colour is switched off automatically when output isn't a terminal, so piping it to
a file gives clean text rather than escape-code soup.

This is the *short* version. `rehearse.sh` (see [`REHEARSAL.md`](./REHEARSAL.md))
runs the fuller 13-step script including the `.rag_off` toggle and the live
add-a-fact. Both call the same `poison_kb.sh` and `reset_demo.sh`, so the two
can't drift apart.
