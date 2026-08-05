# RAG + Knowledge Graph in ~90 lines — an astronomy demo

*A hands-on companion to the LSST / Rubin AI talk. Runs on your laptop, for free.*

Ground an AI assistant in **your own astronomy facts** — automatically, on every
question you ask. No database, no embeddings library, no API key, no account, no
cloud. Python's standard library and a JSON file you can read and edit.

---

## The idea in two lines

- **RAG** (Retrieval-Augmented Generation) = before the model answers, fetch the
  relevant facts and hand them over, so it reasons from *your* knowledge instead
  of its fuzzy memory.
- **A hook** is a small program your AI assistant runs *for you* on every prompt.
  Put RAG in the hook and grounding becomes invisible: you ask, the right facts
  appear, you think about the science instead of about managing context.

The "knowledge graph" is [`astro_kg.json`](./astro_kg.json) — 18 facts about
asteroid families, orbital elements, and the LSST survey. Swap in your own and
the demo grounds the model in whatever domain you care about.

**Where this goes.** Step 1 shows grounding changing a real answer in about ten
seconds. Steps 3 and 4 wire it into Claude Code and Codex as an invisible hook.
Step 5 is the one to run for an audience: an interactive local agent where you
toggle grounding live, edit the knowledge base mid-conversation, and deliberately
poison it to see grounding's failure mode.

---

## Step 1 — See it change a real answer (about a minute)

You need [Ollama](https://ollama.com) (free, runs models locally) and Python 3.9+.

```bash
ollama pull llama3.2
git clone https://github.com/neherdata/lsst-hook-rag-demo.git
cd lsst-hook-rag-demo
python3 demo.py "Why do we use proper elements to find asteroid families?"
```

That asks **the same local model the same question twice** — once from its own
memory, once with the relevant facts from `astro_kg.json` prepended — and streams
both answers so you can watch the difference land. It takes about ten seconds.

**What to watch for.** The ungrounded answer is where it gets interesting. Models
are stochastic, so your wording will differ from ours — but the *shape* of the
mistake is reliable: ungrounded, `llama3.2` tends to flatten "proper elements"
into plain orbital elements, and to pad the definition with attributes that have
nothing to do with it. Three consecutive real runs opened:

> "Proper elements, **also known as orbital elements**, are used to describe..."
>
> "Proper elements, **also known as dynamical orbital elements or semi-major
> orbital elements**..."

They are not the same thing — the distinction between osculating and proper
elements is the entire reason proper elements exist. One run also listed
"spectroscopic properties" and "size and shape" as things proper elements are
computed from. They aren't; proper elements are purely dynamical. Fluent,
confident, and wrong is the failure mode that actually costs you time.

Grounded, the same model on the same question:

> "...they are **nearly-invariant averaged quantities** valid over millions of
> years... less affected by short-term perturbations."

Nothing changed except three lines of your own facts, retrieved automatically.
If your ungrounded run happens to come out clean, ask it again — or try the LSST
alert-stream question below, where invented numbers are easy to spot.

> **No Ollama yet?** Run it anyway. `demo.py` detects that nothing is listening
> and shows you the exact text the hook injects instead, with install steps. You
> can also ask for that view directly with `python3 demo.py --offline`.

### If your laptop can't run a model well: Ollama Cloud

An older or smaller machine may pull `llama3.2` and then grind. Ollama has a
**free cloud tier** for exactly this, and it is a first-class part of the CLI —
not a workaround:

```bash
# opens a browser tab; sign up or log in
ollama signin

python3 demo.py --model gpt-oss:20b-cloud "Why do we use proper elements to find asteroid families?"
```

Account creation needs a real email, so that step is yours — no script can do it
for you. Everything after it is identical: cloud models appear on the **same
`localhost:11434` API** as local ones, so `demo.py`, the hook, OpenCode, and the
MCP server all work unchanged. The only thing that differs is the model name.
Cloud model names end in `-cloud`.

**On the free tier:** it's a genuine $0 tier with hourly and daily caps measured
in tokens rather than a flat request count, and models are labelled *low usage* or
*medium usage* for how quickly they consume the allowance. Pick a **low usage**
model — `gpt-oss:20b-cloud` is the light default used here. A short demo is
roughly 20–30 requests per person, which should sit comfortably inside the free
tier; we could not get exact published figures to promise a hard number, so treat
that as a reasonable expectation rather than a guarantee.

Prefer local when you can: it's genuinely private and works with no network at
all once pulled. Cloud is the escape hatch when the hardware isn't cooperating.

### Try a few more

```bash
python3 demo.py "What is the Vesta family and where do the HED meteorites come from?"
python3 demo.py "How many asteroids will LSST discover, and how big is the alert stream?"
python3 demo.py "How do you link single-night detections into an orbit?"

# off-topic -> injects nothing
python3 demo.py "recommend a good pizza recipe"
```

That last one matters: nothing in the KG matches, so the hook stays silent and
your prompt passes through untouched. Grounding that only speaks when it has
something to add is grounding you can leave switched on.

### Options

These are alternatives, not a sequence — run ONE at a time, not the whole block.

```bash
# no model; show what gets injected
python3 demo.py --offline "..."
```

```bash
# skip the ungrounded call (faster)
python3 demo.py --grounded-only "..."
```

```bash
# any model you've pulled
python3 demo.py --model qwen3.5:2b "..."
```

```bash
# Ollama running elsewhere on your network
python3 demo.py --host http://192.168.1.100:11434 "..."
```

`OLLAMA_MODEL` and `OLLAMA_HOST` work too. A tagged name like `qwen3.5:2b` is
matched exactly — the demo will never quietly hand you a different size. Reasoning
models (`qwen3.5`) think before they answer, so expect a pause; `llama3.2` is the
snappiest choice for a live audience.

---

## Step 2 — Why this lands hardest on a small local model

Large cloud models have enormous recall. RAG keeps them honest about *your*
specifics, but they often muddle through without it.

Small local models have **thin recall**. They know roughly what they saw in
training, and the details go soft — exactly as you just watched `llama3.2` blur
proper elements into osculating ones. **Grounding is what moves a 2 GB model from
"plausible" to "correct."** The technique helps every model; it *rescues* the one
running on your laptop tonight.

---

## Step 3 — The whole trick, in one file

[`ground_with_kg.py`](./ground_with_kg.py) is a **UserPromptSubmit hook**. Claude
Code and Codex both run it right before your prompt reaches the model, handing it
a JSON object on stdin. It:

1. **reads** your prompt from stdin,
2. **searches** `astro_kg.json` — plain keyword overlap, most relevant first,
3. **selects** the top few facts,
4. **injects** them by printing this JSON:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "[grounding facts ...] - Osculating vs proper elements: ..."
  }
}
```

`demo.py` isn't a reimplementation of that — it imports the same `retrieve()` and
`build_context()` functions the hook uses. What you saw in step 1 is what the hook
sends. And `additionalContext` is understood by **both** Claude Code and Codex, so
one script works in both tools unchanged; only the registration file differs.

If anything goes wrong, the hook injects nothing and exits cleanly. It can never
get between you and your question.

---

## Step 4 — Wire it into your coding agent

Now make it invisible. Everything above was a harness to *show* you the effect;
in a real agent the grounding just happens.

### Claude Code

This repo ships [`.claude/settings.json`](./.claude/settings.json) with the hook
already configured:

1. Install Claude Code (`npm install -g @anthropic-ai/claude-code`).
2. From inside your clone, run `claude`. It reads `.claude/settings.json` and
   registers the hook — it may ask once to approve it. Say yes.
3. Ask *"Which spectral class dominates the Eos family?"* The hook grounds it
   silently. `/hooks` confirms a `UserPromptSubmit` hook is active.

To use it in **any** project, copy the `hooks` block into your own
`~/.claude/settings.json` and point the command at wherever you put
`ground_with_kg.py` and `astro_kg.json`.

### Codex

This repo ships [`.codex/hooks.json`](./.codex/hooks.json) — the Codex counterpart,
registering the **same** script under the **same** event:

1. Install Codex (`npm install -g @openai/codex`), version **0.146+**.
2. From inside your clone, run `codex` once. It discovers `.codex/hooks.json` and
   asks you to **trust the grounding hook** — it won't silently run a program a
   cloned repo dropped in your project. Approve it once and it fires on every
   prompt afterward, interactive or headless.
3. Ask an astronomy question — grounded, exactly as in Claude Code.

> **Same script, two tiny registration files.** `ground_with_kg.py` is
> byte-for-byte identical in both tools — the ~90 lines never change. The only
> deltas: how each names the repo root (`$CLAUDE_PROJECT_DIR` vs
> `$(git rev-parse --show-toplevel)`), and that Codex's entry takes an optional
> `timeout`.

> **If you script `codex exec` directly:** an **untrusted** hook is silently
> skipped in headless `exec` — no error, it just doesn't run. Do the interactive
> trust above first, or pass `--dangerously-bypass-hook-trust`. Codex moves fast;
> if grounding ever stops appearing, re-run `codex` interactively to re-approve.
> The retrieval logic is unaffected.

---

## Step 5 — The interactive demo: toggle grounding live, edit the KG live

This is the one to run in front of people. A full-screen local agent where you can
switch grounding **on and off mid-conversation**, **edit the knowledge base while
it's running**, and — the part that actually teaches something — **poison the KB
and watch the model repeat the lie**.

One command, from nothing:

```bash
./start_tui_demo.sh
```

It checks for Ollama, starts the server, pulls the model, installs OpenCode if
missing, self-tests the MCP server, and drops you into the agent. It only installs
what's absent and tells you before it does.

These are alternatives, not a sequence — run ONE at a time, not the whole block.

```bash
# local model (default)
./start_tui_demo.sh
```

```bash
# Ollama Cloud free tier instead
./start_tui_demo.sh --cloud
```

```bash
# set up and verify, don't launch
./start_tui_demo.sh --check
```

```bash
# pick a specific model
MODEL=qwen3.5:2b ./start_tui_demo.sh
```

If the local pull fails — no disk, no network, struggling machine — the script
offers to switch to Ollama Cloud and walks you through `ollama signin`. Both
routes end at the same place: OpenCode plus the MCP grounding server, wired
identically. We've run the full interactive demo on both `llama3.2` locally and
`gpt-oss:20b-cloud` on the free tier.

Already have the tools? `opencode --agent astro` is the whole command.

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

### Rehearsing it

To push the whole sequence through without typing it:

```bash
./rehearse.sh
```

That runs the identical script via `opencode run "<prompt>"` — one call per
prompt, interleaving the same `touch`/`rm`/reset actions — and prints each prompt
with the answer it produced. It resets at the start and at the end, and fails
loudly if the repo isn't clean afterward.

```bash
./rehearse.sh --list
```

prints the script without running anything, which is a handy cue card.

**`rehearse.sh` is not the demo.** Give the talk from the real TUI — an audience
should watch a live session, not a shell script scrolling past. This is the
regression tool: run it before a talk to confirm the flow still behaves.

> **Why separate one-shot runs work.** Every step's state lives in the
> **filesystem** — the contents of `astro_kg.json` and whether `.rag_off` exists —
> not in conversation memory. Each `opencode run` is a fresh session with no
> history, and that's fine: the MCP server re-reads both on every tool call. We
> verified this rather than assumed it. Step 9 retrieves the fact added in step 8,
> and step 11 repeats the lie planted in step 10, *across separate sessions*.

### How this differs from the hook — and why that's the interesting part

OpenCode has **no `UserPromptSubmit` hook**. It integrates through **MCP** (Model
Context Protocol), so grounding can't be silently injected the way steps 3 and 4
do it. Instead, [`astro_mcp.py`](./astro_mcp.py) serves the *same* `astro_kg.json`
through the *same* `retrieve()` and `build_context()` functions as a **tool the
model calls**. That's a genuinely different shape, and it's worth saying out loud:

|  | Hook (Claude Code, Codex) | MCP tool (OpenCode) |
|---|---|---|
| When it fires | Automatically, every prompt | When the model decides to call it |
| Can the model skip it? | No | Yes |
| Can you watch it happen? | No — it's invisible | Yes — you see the tool call |

Neither is better. The hook guarantees grounding; the tool makes grounding
*observable*, which is exactly what you want on a projector. You'll see a line
like `⚙ astro-kg_search_astro_kb {"query":"..."}` before each answer — that's the
retrieval happening in public.

The server is ~200 lines of standard-library Python — JSON-RPC over stdio, no MCP
SDK, no dependencies, consistent with the rest of the repo. It exposes three tools:

| Tool | What it does |
|---|---|
| `search_astro_kb(query)` | Retrieve grounding facts. Honours the on/off flag. |
| `toggle_rag(enabled)` | Turn grounding on or off at runtime. |
| `kg_fact(op, ...)` | `list` / `add` / `edit` / `remove` facts in `astro_kg.json`. |

### 5a. Toggle grounding on and off, mid-conversation

Grounding is ON unless a file called `.rag_off` exists. The flag is re-read on
**every single retrieval call**, so you can flip it from a second terminal without
restarting OpenCode or the MCP server:

Turn grounding OFF:

```bash
touch .rag_off
```

Turn grounding back ON:

```bash
rm .rag_off
```

Keep that second terminal on screen. The demo:

1. Ask: **"What causes the Kirkwood gaps?"** → grounded, precise: mean-motion
   resonances with Jupiter, the 3:1 at ~2.50 AU.
2. Second terminal: `touch .rag_off`
3. Ask **the same question again**. The model announces it is answering
   `UNGROUNDED` and falls back to memory. What comes out is a lottery — one of
   our runs was roughly right, another blamed Jupiter's moons, another described
   a completely different (stellar) phenomenon. Ask it two or three times; the
   instability *is* the demo.
4. `rm .rag_off` and ask once more. Precision and repeatability return.

Nothing restarted. Nothing recompiled. One empty file.

> You can also just say **"turn grounding off"** in the TUI and the model will call
> `toggle_rag` for you. The file is the better stage trick — the audience can see
> the cause.
>
> **Why the tool is always offered, even when grounding is off:** an MCP client
> fetches the tool list once, when it connects. Hiding the tool would need a
> reconnect, which would kill the live-toggle moment. So the tool stays listed and
> the flag is enforced *inside* the call.

### 5b. Edit the knowledge base while the agent is running

Ask, in plain English:

> *"Use kg_fact to add a fact. Topic: 3200 Phaethon. Keywords: phaethon, geminids,
> meteor, shower. Text: 3200 Phaethon is a B-type near-Earth asteroid and the
> parent body of the Geminid meteor shower."*

Then immediately: *"Tell me about the parent body of the Geminids."* The new fact
is retrieved on the very next question — no reindex, no restart, no rebuild.
`kg_fact(op="list")` shows everything currently loaded.

Edits are written atomically and preserve the file's hand-written formatting, so
`astro_kg.json` stays readable and diffable after the agent has touched it.

### 5c. The part worth staying for: grounding is trust, not truth

Everything so far shows grounding making a model *better*. Now break it — this is
the most useful sixty seconds of the demo.

**Poison the knowledge base.** In your second terminal:

```bash
./poison_kb.sh
```

That replaces the true Kirkwood gaps fact with:

> *"The Kirkwood gaps are swept clear by the magnetic field of Jupiter, which
> repels the iron-rich asteroids in those zones and herds them into the Trojan
> swarms."*

Unphysical nonsense — and it sounds perfectly reasonable to anyone who isn't an
astronomer. Nothing restarts; the next retrieval picks it up. Now ask, in the TUI:

> *"What causes the Kirkwood gaps?"*

Here is what we actually got from `llama3.2`, all three ways, same question:

| Grounding | Answer |
|---|---|
| **Off** (own memory) | A lottery. Across four runs: once roughly right (*"gravity perturbations by nearby giant planets"*), once blaming *"Jupiter's moons, particularly Io and Europa"*, once describing Kirkwood gaps as a **binary-star radial-velocity** phenomenon, once no answer at all. |
| **On**, true KB | *"...mean-motion resonances with Jupiter... resonant pumping of eccentricity clears asteroids from these zones"*, with the 3:1 at ~2.50 AU. Right, precise, and repeatable. |
| **On**, poisoned KB | *"The Kirkwood gaps are cleared due to Jupiter's strong magnetic field, which repels the iron-rich objects in those areas, forcing them into the Trojan regions."* — **confidently wrong**, every time. |

Two things to draw out, and the second is the important one.

**Grounding removes variance.** The ungrounded column isn't just "sometimes
wrong" — it's *unstable*. Ask three times, get three different physics. The
grounded column says the same correct thing every time. For a small local model
that consistency is most of the value.

**But consistency is not truth.** The poisoned row is delivered in exactly the
same calm, precise register as the correct one. Nothing in the model's tone,
hedging, or confidence distinguishes "grounded in something true" from "grounded
in something I made up sixty seconds ago." The model isn't evaluating the claim;
it's deferring to it — because we told it to prefer the document over its own
recall, and it did.

**"That's just a 3B model being dumb."** It isn't. We ran the identical test on
`gpt-oss:20b-cloud`, a far more capable model, and it is the more damning result:

> **Ungrounded**, asked what causes the Kirkwood gaps, it answered *correctly* —
> orbital resonances with Jupiter, 3:1 and 5:2, eccentricity pumped until the
> asteroid is ejected. It plainly knew the physics.
>
> **Grounded on the poisoned KB**, same question: *"The Kirkwood gaps are caused
> by Jupiter's magnetic field, which sweeps the iron-rich asteroids out of those
> zones and herds them into the Trojan swarms."*

A model that demonstrably knew the right answer discarded it because a retrieved
document said otherwise. Capability doesn't save you here — arguably the better
the model is at following your instructions, the more faithfully it will repeat
whatever you put in front of it.

**RAG is a trust mechanism, not a truth mechanism.** It moves authority from the
model's weights to your knowledge base. That's exactly what you want — *provided
the knowledge base is right*. Grounding doesn't make a model truthful; it makes it
faithful to a source. Curation, provenance, and review of that source are now part
of your science, not an IT detail. Garbage in, garbage out — delivered fluently,
and in the same voice as the truth.

Put it back:

```bash
./reset_demo.sh
```

That restores `astro_kg.json` from git, clears the `.rag_off` flag, sweeps any
temp files, and tells you what it changed. Ask the question once more afterwards —
the resonances come back, which proves the reset actually worked. Run it before
handing the laptop to the next person; it's safe to run when nothing is dirty.

### 5d. Honest limitations you should know before demoing

- **Retrieval is naive keyword overlap** — about 20 lines, deliberately. It is
  easy to miss. Real example from our testing: *"What causes the Kirkwood gaps?"*
  retrieves the Kirkwood fact, but *"What causes the Kirkwood gaps in the main
  belt?"* retrieves three **asteroid family** facts instead, because "main" and
  "belt" happen to appear in them. And *"Why are there gaps in the asteroid belt?"*
  misses the Kirkwood fact entirely — it ties on score and loses to earlier facts.
  Phrase demo questions in the KB's own vocabulary, or upgrade the retrieval (this
  is exactly the job embeddings do).
- **The model chooses whether to call the tool.** Usually it does; occasionally a
  small model answers without it. The `astro` agent's system prompt pushes hard on
  calling `search_astro_kb` first. The hook path in step 4 has no such gap.
- **`llama3.2` is a 3B model in an agent loop, and it is visibly flaky at tool
  calls.** Measured on this host:

  | Model | Simple question | Add-a-fact prompt |
  |---|---|---|
  | `llama3.2` (local) | 5/6 | 3/4 |
  | `gpt-oss:20b-cloud` | 6/6 | reliable in all runs |

  When it misses, it prints the tool-call JSON as plain text and nothing happens —
  we've seen `astro-kg_search_ astro_kb` with a stray space, a string truncated at
  the apostrophe in "Jupiter's", and a turn that returned no answer at all. **All
  of these fail silently.** That's why Act 4 — the one beat you can't afford to
  lose — is a script (`poison_kb.sh`) rather than a prompt. If a prompt-driven step
  misfires live, just ask again; it usually lands the second time.

  **For a room, consider `./start_tui_demo.sh --cloud`.** Same demo, same free
  tier, materially steadier tool calling. Note this only affects Step 5's agent
  loop — Step 1's `demo.py` makes no tool calls at all and is rock solid on
  `llama3.2`.
  If you want a steadier agent, `gpt-oss:20b-cloud` on the free tier handled the
  same tool calls cleanly every time we tried. The `astro` agent also has file,
  shell and edit tools **disabled** — it can only touch the knowledge base — which
  was added after `llama3.2`, mid-run, tried to edit a file outside the repo.
  Don't take that risk in front of an audience.
- **Reasoning models pause before answering.** `qwen3.5:2b` thinks first, so
  expect a silent gap. `llama3.2` is the snappier choice for a live room.

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

Then `python3 demo.py "tell me about the Geminids parent body"` and it's there.
That's the whole editing workflow — no schema, no migration, no rebuild, no
re-indexing step. Point it at your asteroid families, your observing logs, your
instrument notes.

That's the payload of the talk: **RAG over a knowledge graph is about 90 lines of
standard-library Python in a hook.** Spend your attention on the science — *"could
these two detections be the same object?"* — instead of on hand-managing context.

---

## Files

| File | What it is |
|------|-----------|
| `demo.py` | **Start here.** Asks a local Ollama model the same question with and without your facts, and streams both. `--offline` shows the injected context with no model at all. |
| `ground_with_kg.py` | The hook — reads the prompt, retrieves facts, injects them. ~90 lines, stdlib only. Everything else imports its retrieval rather than reimplementing it. |
| `astro_kg.json` | The knowledge base — asteroid families, orbital elements, LSST facts. Edit freely, by hand or through `kg_fact`. |
| `astro_mcp.py` | MCP server for the interactive demo: `search_astro_kb`, `toggle_rag`, `kg_fact`. Stdlib-only JSON-RPC over stdio. `--selftest` checks it without opening a session. |
| `start_tui_demo.sh` | One-command bootstrap: Ollama, model, OpenCode, MCP check, then launches the agent. `--check` sets up without launching. |
| `rehearse.sh` | Pushes the whole Step 5 script through non-interactively via `opencode run`, for rehearsal and regression. `--list` prints the script as a cue card. |
| `reset_demo.sh` | Puts the repo back: restores `astro_kg.json`, clears `.rag_off`, sweeps temp files. Safe to run any time. |
| `poison_kb.sh` | Act 4: swaps the true Kirkwood fact for a plausible falsehood. Undo with `reset_demo.sh`. |
| `opencode.json` | Registers the Ollama provider, the MCP server, and the tool-restricted `astro` agent. Works on clone. |
| `ask_ollama.py` | Thin alias that forwards to `demo.py`, so older instructions keep working. |
| `.claude/settings.json` | Ready-made Claude Code hook registration (works on clone). |
| `.codex/hooks.json` | Ready-made Codex hook registration (works on clone, after a one-time trust approval). |

## Requirements

Python 3.9+ standard library — that is the entire Python dependency list, for the
hook, the demo script, and the MCP server alike.

You also need a model, and there are two ways to get one:

| Path | What you need | Good for |
|---|---|---|
| **Local** (preferred) | [Ollama](https://ollama.com) + `ollama pull llama3.2` (~2 GB) | Private, offline, free forever |
| **Ollama Cloud** | `ollama signin` (free tier, real email) | Laptops that can't run models well |

Both expose the same `localhost:11434` API, so every script here works with
either — only the model name changes. Step 5 additionally wants
[OpenCode](https://opencode.ai) (`npm install -g opencode-ai`);
`start_tui_demo.sh` installs whatever is missing on either path.

No API key and no paid account anywhere in this repo. On the local path, no
network either, once the model is pulled.

## License

MIT — see [`LICENSE`](./LICENSE). Built by Westover Labs for the LSST / Rubin
astronomer talk. Share it, fork it, point it at your own data.
