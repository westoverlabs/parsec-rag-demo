#!/usr/bin/env python3
"""ground_with_kg.py — a ~90-line RAG + KG grounding hook (Python stdlib only).

WHAT THIS IS
------------
A `UserPromptSubmit` hook. Both Claude Code and OpenAI Codex run a small program
of your choosing every time you hit Enter, BEFORE your prompt reaches the model.
This program:

    1. reads your prompt (the coding agent hands it to us as JSON on stdin),
    2. searches a tiny local knowledge base of astronomy facts (astro_kg.json),
    3. picks the few most relevant facts (plain keyword overlap — no embeddings,
       no database, no network),
    4. injects them into the model's context so it answers grounded in YOUR facts.

That is Retrieval-Augmented Generation (RAG) over a Knowledge Graph (KG), in one
file. The astronomer types a question; the right domain facts show up silently.

It works UNCHANGED in Claude Code and Codex because both accept the same output:
JSON with `hookSpecificOutput.additionalContext`.

FAIL-OPEN: if anything goes wrong we inject nothing and exit 0, so a broken hook
never blocks your prompt. (Never let plumbing get between you and your question.)
"""

import json
import re
import sys
from pathlib import Path

# How many facts to inject. Small on purpose — grounding, not a data dump.
TOP_K = 3
# The knowledge base lives next to this script, so the hook works from any cwd.
KG_PATH = Path(__file__).resolve().parent / "astro_kg.json"

_WORD = re.compile(r"[a-z0-9]+")

# Common words carry no topic signal. Dropping them stops an unrelated prompt
# ("what is the weather today") from matching every fact on shared words like
# "the" or "is". This is the toy version of a real search engine's stop-list.
_STOPWORD_TEXT = """
    a an the of to in on at for and or but is are be by with from as it its
    this that these those we you they i he she what which who how why when
    where do does did can could would should will was were been being have
    has had not no yes about into over under out up down off than then them
    your our their my me us if so such more most some any all one two
"""
_STOPWORDS = frozenset(_STOPWORD_TEXT.split())


def tokens(text: str) -> set[str]:
    """Lowercase, split into word tokens, and drop uninformative stopwords."""
    return {w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS}


def score(prompt_tokens: set[str], fact: dict) -> int:
    """Relevance = how many of the prompt's words appear in this fact.

    We match against the fact's curated `keywords` AND the words in its text,
    so a question phrased in the astronomer's own words still finds the fact.
    Keywords are tokenized the same way as the prompt, so a hyphenated keyword
    like "c-type" splits to {c, type} and still matches "C-type" in a question.
    """
    haystack = tokens(" ".join(fact.get("keywords", []))) | tokens(fact.get("text", ""))
    return len(prompt_tokens & haystack)


def retrieve(prompt: str, facts: list[dict], k: int = TOP_K) -> list[dict]:
    """Return the top-k facts whose keywords best overlap the prompt."""
    pt = tokens(prompt)
    # Score every fact once, keep the ones that matched, best-first, take k.
    scored = [(score(pt, f), f) for f in facts]
    hits = [f for s, f in sorted(scored, key=lambda sf: sf[0], reverse=True) if s > 0]
    return hits[:k]


def build_context(hits: list[dict]) -> str:
    """Format the retrieved facts as a labelled block for the model."""
    header = "[grounding facts from your local astronomy KG — prefer these over your own recall]"
    lines = [header]
    for f in hits:
        lines.append(f"- {f['topic']}: {f['text']}")
    return "\n".join(lines)


def main() -> None:
    # Both Claude Code and Codex send a JSON object on stdin; the user's prompt
    # is under the "prompt" key. We don't care about the other fields here.
    payload = json.load(sys.stdin)
    prompt = payload.get("prompt", "")

    facts = json.loads(KG_PATH.read_text(encoding="utf-8")).get("facts", [])
    hits = retrieve(prompt, facts)

    if not hits:
        # Nothing relevant — inject nothing. The prompt passes through untouched.
        return

    # The one line that makes the magic work: hand the model extra context.
    # This exact JSON shape is understood by BOTH Claude Code and Codex.
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": build_context(hits),
                }
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001,S110 - intentional fail-open: a hook must never block your prompt
        # Fail open: on ANY error we inject nothing and exit 0, so a broken hook
        # or a malformed KG file can never get between you and your question.
        pass
