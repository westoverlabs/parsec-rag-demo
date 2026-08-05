#!/usr/bin/env bash
# poison_kb.sh -- deliberately replace a TRUE fact with a plausible FALSEHOOD.
#
# This is Act 4 of the Step 5 demo. It swaps the Kirkwood gaps fact for an
# unphysical explanation (Jupiter's magnetic field herding iron-rich asteroids)
# that sounds entirely reasonable to anyone who isn't an astronomer. Then you ask
# the agent what causes the Kirkwood gaps, and watch it repeat the lie.
#
#     ./poison_kb.sh          # poison the knowledge base
#     ./reset_demo.sh         # put it back
#
# WHY A SCRIPT AND NOT A PROMPT: you can ask the agent to make this edit with the
# kg_fact tool, and on a capable model it works. But small local models are bad at
# emitting a long verbatim string inside a tool call -- llama3.2 truncated it at
# the apostrophe in "Jupiter's" on one run and emitted malformed JSON on the next,
# so the poisoning silently didn't happen and the punchline died. Doing it from
# the terminal is deterministic, and it's better theatre anyway: the audience
# watches YOU change the source of truth, then watches the model believe you.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

TOPIC="Kirkwood gaps"
FALSE_TEXT="The Kirkwood gaps are swept clear by the magnetic field of Jupiter, which repels the iron-rich asteroids in those zones and herds them into the Trojan swarms."

say()  { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
info() { printf '    %s\n' "$1"; }

say "Poisoning the knowledge base"

TOPIC="$TOPIC" FALSE_TEXT="$FALSE_TEXT" python3 - <<'PY'
import os
import sys

sys.path.insert(0, ".")
from astro_mcp import find_fact, load_facts, save_facts

topic = os.environ["TOPIC"]
false_text = os.environ["FALSE_TEXT"]

facts = load_facts()
index = find_fact(facts, topic)

print(f"    BEFORE: {facts[index]['text'][:100]}...")
facts[index]["text"] = false_text
save_facts(facts)
print(f"    AFTER:  {false_text[:100]}...")
PY

info ""
info "The knowledge base now states something unphysical."
info "Ask the agent:  What causes the Kirkwood gaps?"
info ""
info "Undo with:  ./reset_demo.sh"
printf '\n'
