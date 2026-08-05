#!/usr/bin/env python3
"""astro_mcp.py -- the same KG, exposed to a TUI agent as live MCP tools.

WHY THIS EXISTS
---------------
`ground_with_kg.py` is a UserPromptSubmit *hook*: it fires automatically before
every prompt in Claude Code and Codex. OpenCode has no such hook -- it integrates
through MCP (Model Context Protocol) instead. So to give OpenCode the same
grounding we expose retrieval as a **tool the model can call**.

That difference is worth saying out loud in the talk:

    hook = grounding is automatic and invisible; the model can't opt out.
    MCP  = grounding is a tool the model chooses to call; you can watch it decide.

Same `astro_kg.json`, same `retrieve()` / `build_context()` from the hook -- only
the delivery mechanism changes.

WHAT IT SERVES
--------------
    search_astro_kb(query)   retrieve grounding facts (honours the on/off flag)
    toggle_rag(enabled)      flip grounding on/off at runtime
    kg_fact(op, ...)         list / add / edit / remove facts in astro_kg.json

THE ON/OFF FLAG
---------------
Grounding is ON unless a file named `.rag_off` exists next to this script.
The flag is re-read on EVERY search_astro_kb call, so you can flip it from a
second terminal, mid-conversation, and the very next question behaves differently
with no restart of OpenCode or of this server:

    touch .rag_off     # grounding off
    rm .rag_off        # grounding on

Note that we always *offer* the tool and enforce the flag inside the call. An MCP
client fetches the tool list once when it connects, so hiding the tool would need
a reconnect -- which would break the live-toggle moment we're trying to show.

PROTOCOL
--------
MCP over stdio: JSON-RPC 2.0, one JSON object per line on stdin/stdout.
Implemented here in the standard library only, to keep this repo dependency-free.
stdout is the protocol channel -- all logging goes to stderr.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from ground_with_kg import build_context, retrieve

HERE = Path(__file__).resolve().parent
KG_PATH = HERE / "astro_kg.json"
FLAG_PATH = HERE / ".rag_off"

SERVER_NAME = "astro-kg"
SERVER_VERSION = "1.0.0"
FALLBACK_PROTOCOL = "2024-11-05"


def log(message: str) -> None:
    """Never write logs to stdout -- that's the JSON-RPC channel."""
    print(f"[astro-mcp] {message}", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# The knowledge base
# --------------------------------------------------------------------------


def load_kg() -> dict:
    return json.loads(KG_PATH.read_text(encoding="utf-8"))


def load_facts() -> list[dict]:
    return load_kg().get("facts", [])


def render_kg(kg: dict) -> str:
    """Serialise astro_kg.json in the hand-written style the file already uses.

    json.dumps(indent=2) would explode every keyword list into one line per word
    and silently drop nothing -- but it would reformat all 18 facts into a huge
    diff. This file is meant to be read and edited by humans, so we keep each
    fact's keywords on a single line and preserve any other top-level keys
    (notably the "_comment" header) exactly as they were.
    """
    lines = ["{"]
    for key, value in kg.items():
        if key == "facts":
            continue
        lines.append(f"  {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)},")

    lines.append('  "facts": [')
    facts = kg.get("facts", [])
    for i, fact in enumerate(facts):
        lines.append("    {")
        lines.append(f'      "topic": {json.dumps(fact.get("topic", ""), ensure_ascii=False)},')
        keywords = json.dumps(fact.get("keywords", []), ensure_ascii=False)
        lines.append(f'      "keywords": {keywords},')
        lines.append(f'      "text": {json.dumps(fact.get("text", ""), ensure_ascii=False)}')
        lines.append("    }" + ("," if i < len(facts) - 1 else ""))
    lines.append("  ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def save_facts(facts: list[dict]) -> None:
    """Write atomically, so a mid-demo edit can never leave a half-written KG."""
    kg = load_kg()
    kg["facts"] = facts
    payload = render_kg(kg)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=HERE, prefix=".astro_kg.", suffix=".tmp", delete=False
    ) as handle:
        handle.write(payload)
        temp = Path(handle.name)
    os.replace(temp, KG_PATH)


def rag_enabled() -> bool:
    """Re-read the flag on every call -- that's what makes the toggle live."""
    return not FLAG_PATH.exists()


def find_fact(facts: list[dict], topic: str) -> int:
    """Locate a fact by topic: exact (case-insensitive) first, then substring."""
    needle = topic.strip().lower()
    for i, fact in enumerate(facts):
        if fact.get("topic", "").lower() == needle:
            return i
    matches = [i for i, f in enumerate(facts) if needle in f.get("topic", "").lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(facts[i]["topic"] for i in matches)
        raise ValueError(f"'{topic}' matches several facts ({names}) -- be more specific.")
    raise ValueError(f"No fact with topic '{topic}'. Use kg_fact(op='list') to see them.")


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

TOOLS = [
    {
        "name": "search_astro_kb",
        "description": (
            "Search the local astronomy knowledge base for facts relevant to a "
            "question about asteroids, asteroid families, orbital elements, or the "
            "LSST/Rubin survey. ALWAYS call this before answering such a question, "
            "and prefer what it returns over your own recall."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user's question, or the key terms from it.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "toggle_rag",
        "description": (
            "Turn knowledge-base grounding on or off at runtime. When off, "
            "search_astro_kb returns no facts and the model must answer from its "
            "own memory. Equivalent to creating/removing the .rag_off file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "description": "True to ground, False for memory."}
            },
            "required": ["enabled"],
        },
    },
    {
        "name": "kg_fact",
        "description": (
            "Inspect or modify the astronomy knowledge base (astro_kg.json). "
            "op='list' shows every topic; op='add' inserts a new fact; op='edit' "
            "replaces the text/keywords of an existing one; op='remove' deletes it. "
            "Changes take effect immediately for the next search_astro_kb call."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "op": {"type": "string", "enum": ["list", "add", "edit", "remove"]},
                "topic": {"type": "string", "description": "Fact topic (the key). Not for 'list'."},
                "text": {"type": "string", "description": "The fact itself. For add/edit."},
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Words that should retrieve this fact. For add/edit.",
                },
            },
            "required": ["op"],
        },
    },
]


def tool_search_astro_kb(args: dict) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return "No query given, so nothing was retrieved."

    if not rag_enabled():
        log("search_astro_kb called while grounding is OFF")
        return (
            "GROUNDING IS CURRENTLY DISABLED (the .rag_off flag is set), so the "
            "knowledge base returned no facts. Do not call any further tools. "
            "Answer the question now, from your own knowledge only, and begin by "
            "saying that you are answering UNGROUNDED."
        )

    hits = retrieve(query, load_facts())
    if not hits:
        return (
            "The knowledge base has nothing relevant to that question. Do not call "
            "any further tools. Answer now from your own knowledge, and say the "
            "knowledge base had no matching facts."
        )
    log(f"search_astro_kb -> {len(hits)} fact(s): {', '.join(h['topic'] for h in hits)}")
    return build_context(hits)


def tool_toggle_rag(args: dict) -> str:
    enabled = args.get("enabled")
    if not isinstance(enabled, bool):
        return "toggle_rag needs enabled=true or enabled=false."
    if enabled:
        FLAG_PATH.unlink(missing_ok=True)
        log("grounding ON")
        return "Grounding is now ON. search_astro_kb will return facts again."
    FLAG_PATH.touch()
    log("grounding OFF")
    return "Grounding is now OFF. search_astro_kb will return no facts until re-enabled."


def tool_kg_fact(args: dict) -> str:
    op = (args.get("op") or "").strip().lower()
    facts = load_facts()

    if op == "list":
        listing = "\n".join(f"- {f['topic']}" for f in facts)
        state = "ON" if rag_enabled() else "OFF"
        return f"{len(facts)} fact(s) in the knowledge base (grounding is {state}):\n{listing}"

    topic = (args.get("topic") or "").strip()
    if not topic:
        return f"op='{op}' needs a topic."

    if op == "add":
        text = (args.get("text") or "").strip()
        if not text:
            return "op='add' needs the fact text."
        keywords = args.get("keywords") or []
        if not isinstance(keywords, list) or not keywords:
            # Fall back to the topic's own words so the fact is at least findable.
            keywords = topic.lower().split()
        facts.append({"topic": topic, "keywords": [str(k) for k in keywords], "text": text})
        save_facts(facts)
        log(f"added fact: {topic}")
        return f"Added '{topic}'. It will be retrievable on the very next question."

    try:
        index = find_fact(facts, topic)
    except ValueError as exc:
        return str(exc)

    if op == "edit":
        if args.get("text"):
            facts[index]["text"] = args["text"].strip()
        if isinstance(args.get("keywords"), list) and args["keywords"]:
            facts[index]["keywords"] = [str(k) for k in args["keywords"]]
        save_facts(facts)
        log(f"edited fact: {facts[index]['topic']}")
        return f"Updated '{facts[index]['topic']}'."

    if op == "remove":
        removed = facts.pop(index)
        save_facts(facts)
        log(f"removed fact: {removed['topic']}")
        return f"Removed '{removed['topic']}'. {len(facts)} fact(s) left."

    return f"Unknown op '{op}'. Use list, add, edit, or remove."


HANDLERS = {
    "search_astro_kb": tool_search_astro_kb,
    "toggle_rag": tool_toggle_rag,
    "kg_fact": tool_kg_fact,
}


# --------------------------------------------------------------------------
# JSON-RPC / MCP plumbing
# --------------------------------------------------------------------------


def call_tool(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    handler = HANDLERS.get(name)
    if handler is None:
        return {"content": [{"type": "text", "text": f"Unknown tool '{name}'."}], "isError": True}
    try:
        return {"content": [{"type": "text", "text": handler(args)}]}
    except Exception as exc:  # noqa: BLE001 - a tool error must not kill the server
        log(f"tool {name} failed: {exc!r}")
        return {"content": [{"type": "text", "text": f"Tool error: {exc}"}], "isError": True}


def dispatch(method: str, params: dict) -> dict:
    if method == "initialize":
        # Echo the client's protocol version when it names one -- widest compatibility.
        version = params.get("protocolVersion")
        return {
            "protocolVersion": version if isinstance(version, str) else FALLBACK_PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        return call_tool(params)
    if method == "ping":
        return {}
    # Clients probe these even when we advertise no such capability; answering
    # with an empty list is friendlier than an error.
    if method in ("resources/list", "resources/templates/list"):
        return {"resources": [], "resourceTemplates": []}
    if method == "prompts/list":
        return {"prompts": []}
    raise LookupError(method)


def main() -> None:
    log(f"serving {KG_PATH.name}; grounding {'ON' if rag_enabled() else 'OFF'}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            log(f"ignoring non-JSON line: {line[:80]}")
            continue

        request_id = message.get("id")
        method = message.get("method", "")
        params = message.get("params") or {}

        try:
            result = dispatch(method, params)
        except LookupError:
            if request_id is not None:
                error = {"code": -32601, "message": f"Method not found: {method}"}
                print(json.dumps({"jsonrpc": "2.0", "id": request_id, "error": error}), flush=True)
            continue
        except Exception as exc:  # noqa: BLE001 - stay alive whatever happens
            log(f"dispatch error on {method}: {exc!r}")
            if request_id is not None:
                error = {"code": -32603, "message": str(exc)}
                print(json.dumps({"jsonrpc": "2.0", "id": request_id, "error": error}), flush=True)
            continue

        # No id means it was a notification: acknowledge nothing, per JSON-RPC.
        if request_id is not None:
            print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}), flush=True)


def selftest() -> None:
    """Exercise the server without speaking protocol, so setup scripts can check
    it without opening a stdio session that would block waiting for input."""
    facts = load_facts()
    hits = retrieve("proper elements asteroid families", facts)
    assert facts, "astro_kg.json has no facts"
    assert hits, "retrieval returned nothing for a known-good query"
    assert render_kg(load_kg()) == KG_PATH.read_text(encoding="utf-8"), (
        "the KG serializer does not round-trip this file byte-for-byte"
    )
    for tool in TOOLS:
        assert tool["name"] in HANDLERS, f"tool {tool['name']} has no handler"
    print(
        f"ok: {len(facts)} facts, {len(TOOLS)} tools, "
        f"grounding {'ON' if rag_enabled() else 'OFF'}, KG round-trips cleanly"
    )


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        selftest()
        sys.exit(0)
    try:
        main()
    except (KeyboardInterrupt, BrokenPipeError):
        pass
