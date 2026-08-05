/**
 * PARSEC auto-grounding plugin for opencode.
 *
 * This is opencode's native equivalent of the Claude Code / Codex
 * `UserPromptSubmit` hook. Those tools run `ground_with_kg.py` automatically
 * before every prompt; opencode has no config-declared hooks, but it does have a
 * real plugin API. So we hook `chat.message` (fires on every user message) and
 * append the same grounding facts to the message the model receives.
 *
 * That completes the demo's cohesion story: the SAME retrieval, delivered three
 * ways by each tool's own native mechanism.
 *
 *   Claude Code / Codex : UserPromptSubmit hook  -> additionalContext
 *   opencode (MCP tool) : model calls search_astro_kb (visible on the projector)
 *   opencode (this)     : chat.message plugin     -> auto-injected, no tool call
 *
 * Grounding is reused verbatim from `ground_query.py`, which wraps the exact
 * `retrieve()` / `build_context()` the hook uses and honours the live `.rag_off`
 * toggle. Nothing is reimplemented here.
 *
 * NOTE: this is an OPTIONAL alternative to the visible MCP-tool path. If you run
 * both, the model gets grounded twice (harmless, but redundant). The demo ships
 * with the MCP tool as the default because the *visible* tool call is the point
 * on stage; enable this plugin when you want hook-style automatic grounding
 * instead. See .opencode/plugin/README.md.
 *
 * Fail-open by design: any error injects nothing and the prompt passes through.
 */

import { existsSync } from "node:fs"
import { join } from "node:path"

export default async ({ directory, $ }) => {
  const script = join(directory, "ground_query.py")

  return {
    "chat.message": async (_input, output) => {
      try {
        // Opt-in only. The shipped default demo grounds through the *visible*
        // MCP tool call (the point on stage). This plugin stays inert unless you
        // ask for hook-style automatic grounding, via `./start_tui_demo.sh
        // --plugin` or by exporting PARSEC_PLUGIN_GROUNDING=1 yourself.
        if (process.env.PARSEC_PLUGIN_GROUNDING !== "1") return
        if (!existsSync(script)) return

        // The user's text lives in the message parts. Grab the text parts; we
        // both read the query from them and append grounding back onto the last
        // one. (A brand-new part would need a valid id/sessionID/messageID and
        // opencode rejects one without them -- mutating an existing, already
        // valid part in place sidesteps that entirely.)
        const textParts = (output.parts || []).filter(
          (p) => p && p.type === "text" && typeof p.text === "string",
        )
        const query = textParts
          .map((p) => p.text)
          .join("\n")
          .trim()
        if (!query || textParts.length === 0) return

        // Reuse the exact same retrieval the hook uses. `$` auto-escapes the
        // interpolated query, so this is injection-safe. `.rag_off` is honoured
        // inside ground_query.py, so the live toggle still works.
        const facts = (
          await $`python3 ${script} ${query}`.cwd(directory).quiet().nothrow().text()
        ).trim()
        if (!facts) return

        // Append grounding onto the last user text part -- the same effect as
        // the hook appending additionalContext to the prompt.
        const last = textParts[textParts.length - 1]
        last.text = `${last.text}\n\n${facts}`
      } catch {
        // A grounding plugin must never get between you and your prompt.
      }
    },
  }
}
