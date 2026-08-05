# opencode auto-grounding plugin

`grounding.js` is opencode's native equivalent of the Claude Code / Codex
`UserPromptSubmit` hook. opencode has no config-declared hooks, but it has a real
plugin API — so this plugin hooks `chat.message` (fires on every user message)
and appends the same grounding facts to the prompt the model receives.

That completes the demo's cohesion story — the **same** retrieval, delivered
three ways, each by the tool's own native mechanism:

| Tool | Mechanism | Grounding is… |
|---|---|---|
| Claude Code / Codex | `UserPromptSubmit` hook | automatic, invisible |
| opencode (default) | model calls `search_astro_kb` (MCP tool) | visible on the projector |
| opencode (`--plugin`) | this `chat.message` plugin | automatic, injected |

The plugin reuses `ground_query.py`, which wraps the exact `retrieve()` /
`build_context()` the hook uses and honours the live `.rag_off` toggle. Nothing
is reimplemented in JavaScript.

## It's opt-in

opencode auto-loads everything in `.opencode/plugin/`, so this file is always
*loaded* — but it stays **inert** unless you ask for it. The shipped demo grounds
through the visible MCP tool call on purpose (watching the model *decide* to call
the tool is the point on stage). Turn the plugin on when you'd rather have
hook-style automatic grounding — which is also more reliable, because it doesn't
depend on a small model correctly emitting a tool call:

```bash
./start_tui_demo.sh --plugin
```

or, if you launch opencode yourself:

```bash
PARSEC_PLUGIN_GROUNDING=1 opencode --agent astro --model ollama/llama3.2
```

With the plugin on and the MCP tool still enabled, the model is grounded twice
(once by the plugin, once if it also calls the tool). That's harmless but
redundant; it's why the plugin is off by default.

## Verified

Tested by poisoning the knowledge base, **disabling the MCP tool**, and asking a
question: the model repeated the poisoned fact — proof the plugin (the only
grounding source in that test) actually injected it into the prompt. It also
correctly injects nothing when `.rag_off` is set or when no fact is relevant.
