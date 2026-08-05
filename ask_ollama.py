#!/usr/bin/env python3
"""ask_ollama.py — see grounding change a REAL answer, for free, on your laptop.

`demo.py` shows you what the hook *injects*. This script goes one step further:
it actually asks a local model running in Ollama the same question twice —
once WITHOUT your facts, once WITH them — so you can watch grounding change the
answer. No API key, no cloud, no account: the model runs on your machine.

WHY THIS EXISTS
---------------
Ollama is just a model server — it has no "hook" system of its own, so the
UserPromptSubmit trick in `ground_with_kg.py` can't fire inside plain `ollama
run`. This script is the tiny harness that closes that gap: it calls the SAME
retrieve() + build_context() grounding, then hands the result to Ollama's
HTTP API itself. Same RAG+KG, zero extra dependencies (Python stdlib only).

USE IT
------
    # 1. Install Ollama (https://ollama.com) and pull a small model:
    ollama pull llama3.2            # ~2 GB, runs on a laptop

    # 2. Ask a grounded question:
    python3 ask_ollama.py "Why do we use proper elements to find asteroid families?"

    # Options:
    python3 ask_ollama.py --grounded-only "..."   # skip the ungrounded call (faster)
    OLLAMA_MODEL=qwen2.5:3b python3 ask_ollama.py "..."   # pick a different model
    OLLAMA_HOST=http://localhost:11434 python3 ask_ollama.py "..."   # or Ollama Cloud

Off-topic questions retrieve nothing, so the two answers come out identical —
that's the point: grounding only speaks up when it has something to add.

NOTE ON WHY THIS MATTERS MORE HERE THAN IN A BIG CLOUD MODEL: small local
models have the thinnest built-in recall, so RAG grounding closes the widest
gap on exactly the model you're running tonight. Say this in the README too.
"""

import json
import os
import sys
import urllib.request
import urllib.error

from ground_with_kg import build_context, retrieve

DEFAULT_QUESTION = "Why do we use proper elements to find asteroid families?"
MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
RULE = "=" * 72


def load_facts() -> list[dict]:
    from pathlib import Path
    kg = Path(__file__).resolve().parent / "astro_kg.json"
    return json.loads(kg.read_text(encoding="utf-8")).get("facts", [])


def ask(prompt: str) -> str:
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        f"{HOST}/api/generate", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        response_data = json.loads(resp.read())
        # Some models (like Qwen) include a 'thinking' field; strip it and return just the response.
        return response_data.get("response", "").strip()


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--grounded-only"]
    grounded_only = "--grounded-only" in sys.argv[1:]
    question = " ".join(args).strip() or DEFAULT_QUESTION

    hits = retrieve(question, load_facts())
    grounded_prompt = f"{build_context(hits)}\n\n{question}" if hits else question

    print(RULE)
    print(f"QUESTION   (model: {MODEL} via {HOST})")
    print(RULE)
    print(question)
    print()

    try:
        if not grounded_only:
            print(RULE)
            print("WITHOUT grounding — the model answers from memory alone")
            print(RULE)
            print(ask(question))
            print()

        print(RULE)
        print("WITH grounding — the hook's facts prepended to your question")
        print(RULE)
        if hits:
            print(f"(injected {len(hits)} fact(s): " + ", ".join(h["topic"] for h in hits) + ")\n")
        else:
            print("(no matching facts — grounding stays silent; this answer equals the ungrounded one)\n")
        print(ask(grounded_prompt))
    except (urllib.error.URLError, TimeoutError) as e:
        # URLError: network/connection issues. TimeoutError: model too slow (especially with thinking modes).
        # If it's an HTTP error with a response body, try to surface it (e.g., "model not found, try: ollama pull ...").
        error_detail = str(e.reason) if isinstance(e, urllib.error.URLError) else "Model response timeout"
        if isinstance(e, urllib.error.URLError) and hasattr(e, "fp") and e.fp:
            try:
                body = e.fp.read().decode("utf-8", errors="ignore")
                if body:
                    error_detail += f"\n{body}"
            except Exception:
                pass
        sys.exit(
            f"\nCould not reach Ollama at {HOST} ({error_detail}).\n"
            f"Is it running? Start it with `ollama serve`, and make sure you've\n"
            f"pulled the model:  ollama pull {MODEL}\n"
        )


if __name__ == "__main__":
    main()
