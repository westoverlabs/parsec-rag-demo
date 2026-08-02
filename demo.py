#!/usr/bin/env python3
"""demo.py — see the hook's effect WITHOUT configuring anything.

Run it and read the two panels: what the model would see WITHOUT grounding,
and WITH grounding (your prompt plus the facts the hook silently retrieved).

    python3 demo.py
    python3 demo.py "How are asteroid families identified?"
    python3 demo.py "What will LSST's alert stream look like?"

This is exactly what `ground_with_kg.py` injects when it runs as a real hook
inside Claude Code or Codex — here we just print it so you can see the magic.
"""

import sys

from ground_with_kg import build_context, retrieve

# A default question if you don't pass one on the command line.
DEFAULT_QUESTION = "Why do we use proper elements to find asteroid families?"

RULE = "=" * 72


def load_facts() -> list[dict]:
    import json
    from pathlib import Path

    kg = Path(__file__).resolve().parent / "astro_kg.json"
    return json.loads(kg.read_text(encoding="utf-8")).get("facts", [])


def main() -> None:
    question = " ".join(sys.argv[1:]).strip() or DEFAULT_QUESTION
    hits = retrieve(question, load_facts())

    print(RULE)
    print("YOUR QUESTION")
    print(RULE)
    print(question)
    print()

    print(RULE)
    print("WITHOUT the hook  — what the model sees")
    print(RULE)
    print(question)
    print("(the model answers from memory alone — it may guess or drift)")
    print()

    print(RULE)
    print("WITH the hook  — what the model sees")
    print(RULE)
    if hits:
        print(build_context(hits))
        print()
        print(question)
        print("(the model now answers grounded in YOUR verified facts)")
    else:
        print(question)
        print("(no matching facts — the hook stays quiet and your prompt passes")
        print(" through untouched, exactly as if the hook weren't there)")


if __name__ == "__main__":
    main()
