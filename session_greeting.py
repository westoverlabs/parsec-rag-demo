#!/usr/bin/env python3
"""session_greeting.py -- a SessionStart hook that welcomes you into the demo.

WHAT THIS IS
------------
Claude Code and Codex both fire a `SessionStart` hook when a session begins,
BEFORE you type anything. Like the `UserPromptSubmit` hook in ground_with_kg.py,
it returns JSON with `hookSpecificOutput.additionalContext`, and both tools accept
the same shape -- so this one file works in both, exactly like the grounding hook.

Its job is orientation, not grounding: it tells the assistant what this repo is
and asks it to greet you, so someone who has just cloned the repo and typed
`claude` isn't staring at an empty prompt wondering what to do.

WHY THE WORDING IS WHAT IT IS
-----------------------------
The audience for this demo is scientists who write Python and live in a terminal
perfectly happily -- but for many of them this is the first time in a *persistent
conversational* terminal UI, as opposed to running a script and reading its
output. So the greeting orients to the paradigm, not to the terminal: it's a
conversation rather than a one-shot command, the reply streams in, tool calls
appear inline mid-answer (that's retrieval working, not an error), and here's how
to leave. It does NOT explain what a terminal or Python is.

It deliberately does NOT duplicate the Step 5 script from the README. A pointer
beats a copy: three places holding the same list is three places to drift.

FAIL-OPEN: any error and we print nothing and exit 0, so a broken greeting can
never stop a session from starting.
"""

import json
import sys

GREETING = """\
A session in this repo has just started. Before the user says anything, greet \
them briefly and warmly, in your own words, covering exactly these points and \
nothing more:

1. What this repo is: a small hands-on demo showing how RAG (Retrieval-Augmented \
Generation) grounds an AI assistant in a local knowledge base of astronomy facts \
-- asteroid families, orbital elements, the LSST/Rubin survey. It runs entirely \
on their machine: no API key, no cloud account.

2. How this interface works, for someone whose terminal habits are scripts and \
one-shot commands rather than chat sessions. Make these concrete and quick:
   - This is a running conversation, not a single command. Type a question, press \
Enter, and keep going -- context carries between messages.
   - The answer streams in as it is generated, so it appears a piece at a time.
   - You may see a tool call appear inline in the middle of an answer. That is \
the grounding hook fetching facts. It is the demo working, not an error.
   - Mention how to leave the session (Ctrl-C, or /exit).

3. Offer them a starting point. The fastest way to SEE the effect is one command \
in a second terminal, which asks a local model the same question with and without \
the facts:
       python3 demo.py "Why do we use proper elements to find asteroid families?"
   And they can simply ask you an astronomy question right here -- suggest \
"Why do we use proper elements to find asteroid families?" or "What causes the \
Kirkwood gaps?" -- and the grounding hook will feed you the relevant facts \
automatically, without them doing anything.

Point at the README for the full walkthrough. Keep the whole greeting to a short \
paragraph or two plus the example command -- it is a welcome, not a tutorial. Do \
not list the demo's later steps; the README covers those."""


# Shown to the USER at startup, if the tool supports it. The additionalContext
# above only reaches the MODEL, and a model does not speak until spoken to -- so
# without this banner nothing appears until the user types something.
BANNER = """\
Welcome to the PARSEC RAG demo -- grounding an AI assistant in a local astronomy
knowledge base. Everything runs on your machine: no API key, no cloud account.

This is a conversation, not a one-shot command: type a question, press Enter, and
keep going. Answers stream in a piece at a time, and a tool call may appear
mid-answer -- that is the grounding hook fetching facts, not an error.
Ctrl-C, or /exit, to leave.

Try asking:  Why do we use proper elements to find asteroid families?
Or, in another terminal, watch grounding change a real answer:
    python3 demo.py "Why do we use proper elements to find asteroid families?"
"""


def main() -> None:
    # Both Claude Code and Codex hand the hook a JSON object on stdin. We don't
    # need anything from it -- the greeting is the same however the session began
    # -- but we read it so the pipe is consumed cleanly.
    try:
        json.load(sys.stdin)
    except Exception:  # noqa: BLE001 - no payload, or malformed: greet anyway
        pass

    print(
        json.dumps(
            {
                "systemMessage": BANNER,
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": GREETING,
                },
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001,S110 - a greeting must never block a session
        pass
