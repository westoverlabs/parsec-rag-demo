#!/usr/bin/env python3
"""ground_query.py -- one query in (argv), grounding facts out (stdout).

A thin wrapper around the SAME retrieval the Claude Code / Codex hook uses
(`retrieve` + `build_context` from ground_with_kg.py) so the opencode plugin can
reuse it verbatim instead of reimplementing TF-IDF in JavaScript. Prints the
grounding block on stdout, or nothing at all when there's nothing to add.

    python3 ground_query.py "What causes the Kirkwood gaps?"

Unlike the hook, this honours the live `.rag_off` toggle: if that flag file
exists next to this script, grounding is OFF and we print nothing -- so the
opencode plugin behaves exactly like the MCP server's on/off switch.

Fail-open: on ANY error we print nothing and exit 0, so a broken KG can never
wedge the plugin (which would wedge the user's prompt).
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KG_PATH = HERE / "astro_kg.json"
FLAG_PATH = HERE / ".rag_off"


def main() -> None:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        return
    if FLAG_PATH.exists():  # grounding toggled off -- inject nothing
        return

    import json

    from ground_with_kg import build_context, retrieve

    facts = json.loads(KG_PATH.read_text(encoding="utf-8")).get("facts", [])
    hits = retrieve(query, facts)
    if not hits:
        return
    sys.stdout.write(build_context(hits))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001,S110 - fail open, exactly like the hook
        pass
