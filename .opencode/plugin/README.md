# PARSEC Greeting Plugin for opencode

An orientation plugin that provides a one-time greeting and guide when starting a new opencode session with the PARSEC RAG demo.

## Installation

Install the plugin into your opencode configuration:

```bash
cd /path/to/parsec-rag-demo
npm link .opencode/plugin
opencode plugin parsec-greeting-plugin
```

Or, if publishing to npm:

```bash
opencode plugin parsec-greeting-plugin
```

## What It Does

On the first user message in a new session, the plugin:

1. Injects orientation context into the model's system prompt
2. Provides a warm greeting explaining what the demo is about
3. Explains how the interface works (streaming responses, tool calls, etc.)
4. Suggests example questions to ask
5. Points to the README for the full walkthrough

On subsequent messages in the same session, the greeting is not repeated.

## How It Works

The plugin uses opencode's `onChatMessage` hook to detect the first user message in a session. Unlike Claude Code and Codex, which can display a `systemMessage` before any user input via `SessionStart` hooks, opencode's plugin API does not support pre-input messages in version 1.18.13. Instead, this plugin integrates the greeting into the normal conversation flow:

- The greeting context is injected into the model's system instructions on the first turn
- The model naturally incorporates this into its first response
- The user sees guidance and orientation as part of the assistant's opening message
- Subsequent user messages proceed normally without repetition

## Trade-offs vs. Claude Code/Codex SessionStart

**Claude Code / Codex:**
- Display a banner message immediately when the session starts (before user input)
- Inject system context to guide the model
- Greeting is guaranteed to appear first, before any user prompt

**opencode with this plugin:**
- Greeting is delivered as part of the model's first response
- User types their first question, then the assistant responds with greeting + answer
- More conversational flow, but greeting appears "in-stream" rather than pre-input
- Works within opencode 1.18.13's actual plugin capabilities

## Developer Notes

The plugin avoids the known limitations in opencode 1.18.13:
- Does not use `console.log` (corrupts the TUI render channel)
- Does not use `tui.showToast()` (unreliable rendering in this version)
- Does not rely on `session.created` event (fires after first prompt, too late)

Instead, it hooks into `onChatMessage` for reliable, working integration with the chat flow.
