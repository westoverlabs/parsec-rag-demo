# Rehearsing the demo (presenter / dev only)

Not part of the audience walkthrough — this is the non-interactive regression
runner you use to confirm the flow still behaves before you present.

### Non Interactive Version: Rehearsing it

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
