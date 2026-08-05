#!/usr/bin/env python3
"""demo.py -- watch RAG grounding change a REAL answer, on your own laptop.

This is the front door of the repo. It asks a local model (running in Ollama,
on your machine) the SAME question twice:

    1. WITHOUT grounding -- the model answers from memory alone.
    2. WITH grounding    -- the same model, same question, but with the few
                            relevant facts from astro_kg.json prepended.

The retrieval it uses is not a special demo path: it calls the very same
`retrieve()` + `build_context()` functions that `ground_with_kg.py` runs as a
real `UserPromptSubmit` hook inside Claude Code and Codex. What you see here is
exactly what the hook injects there.

    python3 demo.py
    python3 demo.py "How are asteroid families identified?"
    python3 demo.py --offline          # no model needed: show what gets injected
    python3 demo.py --grounded-only    # skip the ungrounded call (faster)
    python3 demo.py --model qwen3.5:2b "..."

No API key, no cloud, no account. The model runs on your machine.

WHY A LOCAL MODEL MAKES THE BEST DEMO: small models have the thinnest built-in
recall, so grounding closes the widest gap on exactly the model you can run on a
laptop tonight. Ungrounded, a 2 GB model will happily invent plausible detail.
Grounded, it answers from your facts.

If Ollama isn't installed or running, this script does NOT fail -- it falls back
to `--offline` mode and shows you the injected context instead, with a one-line
note on how to get the real thing.
"""

from __future__ import annotations  # so the type hints below work on Python 3.9

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from ground_with_kg import build_context, retrieve

DEFAULT_QUESTION = "Why do we use proper elements to find asteroid families?"
DEFAULT_MODEL = "llama3.2"
KG_PATH = Path(__file__).resolve().parent / "astro_kg.json"

RULE = "-" * 72
CONNECT_TIMEOUT = 5  # seconds -- just probing whether Ollama is up
ANSWER_TIMEOUT = 300  # seconds -- generous: first load of a model can be slow


# --------------------------------------------------------------------------
# Talking to Ollama (stdlib only -- no `requests`, no ollama SDK)
# --------------------------------------------------------------------------


def list_models(host: str) -> list[str] | None:
    """Return the models Ollama has locally, or None if Ollama isn't reachable."""
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=CONNECT_TIMEOUT) as resp:
            return [m["name"] for m in json.loads(resp.read()).get("models", [])]
    except Exception:  # noqa: BLE001 - any failure here just means "no Ollama"
        return None


def stream_answer(host: str, model: str, prompt: str) -> None:
    """Ask the model and print tokens as they arrive, so the demo feels alive."""
    body = json.dumps({"model": model, "prompt": prompt, "stream": True}).encode()
    req = urllib.request.Request(
        f"{host}/api/generate", data=body, headers={"Content-Type": "application/json"}
    )
    thinking_noted = False
    with urllib.request.urlopen(req, timeout=ANSWER_TIMEOUT) as resp:
        for line in resp:
            if not line.strip():
                continue
            chunk = json.loads(line)
            # Reasoning models (qwen3.5 etc.) stream a separate "thinking" field
            # before any answer. We don't print the reasoning -- it would swamp
            # the contrast -- but we say it's happening, so a 40-second pause
            # doesn't look like a hang in front of an audience.
            if chunk.get("thinking") and not thinking_noted:
                thinking_noted = True
                sys.stdout.write("[the model is thinking...]\n")
                sys.stdout.flush()
            piece = chunk.get("response", "")
            if piece:
                sys.stdout.write(piece)
                sys.stdout.flush()
            if chunk.get("done"):
                break
    print()


def timed_answer(host: str, model: str, prompt: str) -> None:
    started = time.monotonic()
    stream_answer(host, model, prompt)
    print(f"{RULE}\n({time.monotonic() - started:.1f}s)\n")


# --------------------------------------------------------------------------
# Picking a model that actually exists on this machine
# --------------------------------------------------------------------------


def resolve_model(available: list[str], wanted: str, explicit: bool) -> str | None:
    """Match `wanted` against locally-pulled models.

    Rules, in order:
      1. An exact match always wins.
      2. A bare name ("llama3.2") may match any tag of it ("llama3.2:latest").
      3. A TAGGED name ("qwen3.5:2b") must match exactly -- never fall back to a
         different tag. Tags are usually sizes, and quietly running the 9b when
         someone asked for the 2b turns a 10-second demo into a 5-minute wait.
      4. Only if the user never named a model do we substitute whatever they
         have. A room full of laptops has a room full of different models
         pulled, and the demo should still run.
    """
    if wanted in available:
        return wanted
    if ":" not in wanted:
        for name in available:
            if name.split(":")[0] == wanted:
                return name
    if explicit or not available:
        return None
    return available[0]


# --------------------------------------------------------------------------
# Offline mode -- no model, just show what the hook injects
# --------------------------------------------------------------------------


def show_offline(question: str, hits: list[dict]) -> None:
    print(f"{RULE}\nWITHOUT the hook -- what the model receives\n{RULE}")
    print(question)
    print("\n(the model answers from memory alone -- it may guess or drift)\n")

    print(f"{RULE}\nWITH the hook -- what the model receives\n{RULE}")
    if hits:
        print(build_context(hits))
        print(f"\n{question}")
        print("\n(the model now answers grounded in YOUR verified facts)")
        print("\nThat injected block is byte-for-byte what ground_with_kg.py hands to")
        print("Claude Code and Codex on every prompt. Run without --offline to watch")
        print("a real model answer both ways.")
    else:
        print(question)
        print("\n(no matching facts -- the hook stays quiet and your prompt passes")
        print(" through untouched, exactly as if the hook weren't there)")


# --------------------------------------------------------------------------


def main() -> None:
    argv = sys.argv[1:]
    flags = {a for a in argv if a.startswith("--")}
    unknown = flags - {"--offline", "--dry-run", "--grounded-only", "--model", "--host"}
    if unknown:
        sys.exit(f"Unknown option(s): {', '.join(sorted(unknown))}\n\n{__doc__}")

    # `--model X` / `--host X` may also come from the environment.
    def take_value(flag: str, env: str, default: str) -> tuple[str, bool]:
        if flag in argv:
            i = argv.index(flag)
            if i + 1 >= len(argv):
                sys.exit(f"{flag} needs a value, e.g. {flag} {default}")
            value = argv[i + 1]
            del argv[i : i + 2]
            return value, True
        if env in os.environ:
            return os.environ[env], True
        return default, False

    model, model_explicit = take_value("--model", "OLLAMA_MODEL", DEFAULT_MODEL)
    host, _ = take_value("--host", "OLLAMA_HOST", "http://localhost:11434")
    host = host.rstrip("/")

    offline = bool({"--offline", "--dry-run"} & flags)
    grounded_only = "--grounded-only" in flags
    question = " ".join(a for a in argv if not a.startswith("--")).strip() or DEFAULT_QUESTION

    facts = json.loads(KG_PATH.read_text(encoding="utf-8")).get("facts", [])
    hits = retrieve(question, facts)
    grounded_prompt = f"{build_context(hits)}\n\n{question}" if hits else question

    # ---- Decide whether we can talk to a real model -----------------------
    available = None if offline else list_models(host)
    if not offline:
        if available is None:
            print(f"Ollama isn't answering at {host}, so this is the offline view.\n")
            print("To see a REAL model change its answer (free, ~2 GB, no account):")
            print("    1. install Ollama       https://ollama.com")
            print("    2. ollama serve         (in another terminal)")
            print(f"    3. ollama pull {DEFAULT_MODEL}")
            print("    4. re-run this command\n")
            offline = True
        else:
            resolved = resolve_model(available, model, model_explicit)
            if resolved is None:
                print(f"Ollama is running at {host}, but '{model}' isn't pulled.\n")
                print(f"    ollama pull {model}")
                if available:
                    print(f"\nOr use one you already have: {', '.join(available[:6])}")
                print("\nShowing the offline view in the meantime.\n")
                offline = True
            else:
                # A bare `llama3.2` resolving to `llama3.2:latest` is the same
                # model -- only announce a genuine substitution.
                if resolved.split(":")[0] != model.split(":")[0]:
                    print(f"('{model}' isn't pulled; using '{resolved}', which you have.)\n")
                model = resolved

    # ---- Header ----------------------------------------------------------
    where = "offline -- no model called" if offline else f"model: {model}  via {host}"
    print(RULE)
    print(f"RAG + Knowledge Graph grounding  ({where})")
    print(RULE)
    print(f"\nQUESTION\n  {question}\n")

    if offline:
        show_offline(question, hits)
        return

    # ---- The actual demo: same model, same question, twice ---------------
    try:
        if not grounded_only:
            print("[1/2] WITHOUT grounding -- from the model's own memory.")
            print("      Watch for confident detail that isn't quite right.")
            print(RULE)
            timed_answer(host, model, question)

        if hits:
            print(f"The hook retrieved {len(hits)} fact(s) from astro_kg.json:")
            for h in hits:
                print(f"  - {h['topic']}")
            print()
            print("[2/2] WITH grounding -- same model, same question, your facts first.")
        else:
            print("No fact matched this question, so grounding stays silent and this")
            print("answer is the ungrounded one. That restraint is the feature.")
            print()
            print("[2/2] WITH grounding -- nothing was injected.")
        print(RULE)
        timed_answer(host, model, grounded_prompt)

    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        detail = getattr(exc, "reason", None) or exc
        sys.exit(
            f"\n\nLost contact with Ollama at {host} ({detail}).\n"
            f"Is it still running? Start it with `ollama serve`, and check the\n"
            f"model is pulled:  ollama pull {model}\n"
            f"You can always see what the hook injects with: python3 demo.py --offline\n"
        )

    # ---- The punchline ---------------------------------------------------
    if hits and not grounded_only:
        print("Same model. Same question. The only difference is a few lines of your")
        print("own facts, retrieved and injected automatically. That's RAG over a")
        print("knowledge graph -- and ground_with_kg.py does it in ~90 lines of")
        print("standard-library Python, with no database and no embeddings.")
        print()
        print("Next:  python3 demo.py --offline    (see the exact injected block)")
        print("Then:  wire it into Claude Code or Codex -- see the README.")


if __name__ == "__main__":
    main()
