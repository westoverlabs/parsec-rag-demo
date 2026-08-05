#!/usr/bin/env python3
"""ask_ollama.py -- kept as an alias. The Ollama demo now lives in demo.py.

demo.py IS the Ollama demo: it asks a local model the same question with and
without your KG facts. This shim just forwards to it so older instructions and
slides keep working.

    python3 demo.py "Why do we use proper elements to find asteroid families?"
"""

import os
import runpy
import sys
from pathlib import Path

print("note: ask_ollama.py is now demo.py -- forwarding.\n", file=sys.stderr)

demo = Path(__file__).resolve().parent / "demo.py"
sys.argv = [str(demo), *sys.argv[1:]]
sys.path.insert(0, str(demo.parent))
os.chdir(demo.parent)
runpy.run_path(str(demo), run_name="__main__")
