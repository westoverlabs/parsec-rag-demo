#!/usr/bin/env python3
"""ground_with_kg.py — TF-IDF cosine similarity RAG + KG grounding hook."""

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

TOP_K = 3
KG_PATH = Path(__file__).resolve().parent / "astro_kg.json"

_WORD = re.compile(r"[a-z0-9]+")
_STOPWORD_TEXT = """
    a an the of to in on at for and or but is are be by with from as it its
    this that these those we you they i he she what which who how why when
    where do does did can could would should will was were been being have
    has had not no yes about into over under out up down off than then them
    your our their my me us if so such more most some any all one two
"""
_STOPWORDS = frozenset(_STOPWORD_TEXT.split())


def tokens(text: str) -> list[str]:
    """Lowercase, split into word tokens, and drop uninformative stopwords."""
    return [w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS]


def _compute_idfs(facts: list[dict]) -> dict:
    """Compute IDF (inverse document frequency) for all terms in the corpus."""
    num_facts = len(facts)
    if num_facts == 0:
        return {}

    doc_freq = Counter()
    for fact in facts:
        fact_text = " ".join(fact.get("keywords", [])) + " " + fact.get("text", "")
        fact_terms = set(tokens(fact_text))
        doc_freq.update(fact_terms)

    idfs = {}
    for term, df in doc_freq.items():
        if df > 0:
            idfs[term] = math.log(num_facts / df)
    return idfs


def _tfidf_vector(term_list: list[str], idfs: dict) -> dict:
    """Compute TF-IDF vector: {term: tf * idf} for all terms."""
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
    """Cosine similarity between two TF-IDF vectors (dicts)."""
    dot_product = sum(
        vec_a.get(term, 0) * vec_b.get(term, 0)
        for term in set(vec_a.keys()) | set(vec_b.keys())
    )

    mag_a = math.sqrt(sum(v**2 for v in vec_a.values()))
    mag_b = math.sqrt(sum(v**2 for v in vec_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot_product / (mag_a * mag_b)


def score(query_vector: dict, fact: dict, idfs: dict) -> float:
    """Score a fact using TF-IDF cosine similarity against the query vector."""
    fact_text = " ".join(fact.get("keywords", [])) + " " + fact.get("text", "")
    fact_terms = tokens(fact_text)
    fact_vector = _tfidf_vector(fact_terms, idfs)
    return _cosine_similarity(query_vector, fact_vector)


def retrieve(prompt: str, facts: list[dict], k: int = TOP_K) -> list[dict]:
    """Return the top-k facts by TF-IDF cosine similarity to the prompt."""
    prompt_terms = tokens(prompt)

    if not prompt_terms:
        return []

    idfs = _compute_idfs(facts)

    query_vector = _tfidf_vector(prompt_terms, idfs)

    if not query_vector:
        return []

    scored = []
    for fact in facts:
        sim = score(query_vector, fact, idfs)
        if sim > 0:
            scored.append((sim, fact))

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
    payload = json.load(sys.stdin)
    prompt = payload.get("prompt", "")

    facts = json.loads(KG_PATH.read_text(encoding="utf-8")).get("facts", [])
    hits = retrieve(prompt, facts)

    if not hits:
        return

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
    except Exception:
        pass
