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
import math
import re
import sys
from collections import Counter
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


def tokens(text: str) -> list[str]:
    """Lowercase, split into word tokens, and drop uninformative stopwords.

    Returns a list (preserving multiplicity for TF calculation).
    """
    return [w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS]


def _compute_idfs(facts: list[dict]) -> dict:
    """Compute IDF (inverse document frequency) for all terms in the corpus.

    IDF(term) = log(N / df) where N is total facts and df is count of facts
    containing the term. This weights rare, discriminative terms highly.
    """
    num_facts = len(facts)
    if num_facts == 0:
        return {}

    # Count how many facts contain each term
    doc_freq = Counter()
    for fact in facts:
        fact_text = " ".join(fact.get("keywords", [])) + " " + fact.get("text", "")
        fact_terms = set(tokens(fact_text))  # Use set to count each term once per fact
        doc_freq.update(fact_terms)

    # Compute IDF: log(N / df), avoiding division by zero
    idfs = {}
    for term, df in doc_freq.items():
        if df > 0:
            idfs[term] = math.log(num_facts / df)
    return idfs


def _tfidf_vector(term_list: list[str], idfs: dict) -> dict:
    """Compute TF-IDF vector: {term: tf * idf} for all terms.

    TF (term frequency) = count(term) / total_terms.
    TF-IDF = TF * IDF.
    Returns a dict mapping term -> score, excluding terms not in idfs.
    """
    if not term_list:
        return {}

    tf = Counter(term_list)
    total = len(term_list)

    vector = {}
    for term, count in tf.items():
        if term in idfs:
            vector[term] = (count / total) * idfs[term]
    return vector


def _cosine_similarity(vec_a: dict, vec_b: dict) -> float:
    """Cosine similarity between two TF-IDF vectors (dicts).

    similarity = dot(A, B) / (|A| * |B|)
    Returns 0 if either vector is empty or both are zero-vectors.
    """
    # Dot product
    dot_product = sum(vec_a.get(term, 0) * vec_b.get(term, 0)
                      for term in set(vec_a.keys()) | set(vec_b.keys()))

    # Magnitudes
    mag_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot_product / (mag_a * mag_b)


def retrieve(prompt: str, facts: list[dict], k: int = TOP_K) -> list[dict]:
    """Return the top-k facts by TF-IDF cosine similarity to the prompt.

    Uses term frequency-inverse document frequency (TF-IDF) to score facts:
    rare, discriminative terms in the prompt are weighted more heavily,
    avoiding the naive keyword-overlap problem where common words in
    multiple facts create spurious matches.
    """
    # Tokenize prompt
    prompt_terms = tokens(prompt)

    # If prompt has no content terms, return nothing (fail-open)
    if not prompt_terms:
        return []

    # Build IDF table across all facts
    idfs = _compute_idfs(facts)

    # TF-IDF vector for the query
    query_vector = _tfidf_vector(prompt_terms, idfs)

    # If query vector is empty (no overlap with corpus terms), return nothing
    if not query_vector:
        return []

    # Score each fact by cosine similarity
    scored = []
    for fact in facts:
        fact_text = " ".join(fact.get("keywords", [])) + " " + fact.get("text", "")
        fact_terms = tokens(fact_text)
        fact_vector = _tfidf_vector(fact_terms, idfs)

        sim = _cosine_similarity(query_vector, fact_vector)
        if sim > 0:
            scored.append((sim, fact))

    # Sort by similarity (highest first) and return top-k
    hits = [f for s, f in sorted(scored, key=lambda sf: sf[0], reverse=True)]
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
