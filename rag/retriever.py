"""
retriever.py — Query ChromaDB and build LLM-ready context.

Public API:
    retrieve(query, n_results, doc_type) -> list[dict]
    build_context(query, affected_services, max_docs) -> str
    check_demo_response(query, threshold) -> str | None
"""

from __future__ import annotations

import logging
import re
from typing import Any

from rag.vector_store import search_similar


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level retrieval
# ---------------------------------------------------------------------------
def retrieve(
    query: str,
    n_results: int = 5,
    doc_type: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve the top-K most similar documents as a list of dicts."""
    if not query or not query.strip():
        return []

    results = search_similar(query, n_results=n_results, doc_type=doc_type)

    ids = (results.get("ids") or [[]])[0]
    docs = (results.get("documents") or [[]])[0]
    metas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    out: list[dict[str, Any]] = []
    for i, doc_id in enumerate(ids):
        out.append({
            "id": doc_id,
            "text": docs[i] if i < len(docs) else "",
            "metadata": metas[i] if i < len(metas) else {},
            "distance": distances[i] if i < len(distances) else None,
        })
    return out


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------
def build_context(
    query: str = "",
    affected_services: list[str] | None = None,
    max_docs: int = 8,
) -> str:
    """Build a context string that combines relevant documents from the store."""
    all_docs: list[dict[str, Any]] = []

    if query and query.strip():
        try:
            all_docs.extend(retrieve(query, n_results=4))
        except Exception as exc:
            logger.warning("Query retrieval failed: %s", exc)

    if affected_services:
        for svc in affected_services[:4]:
            try:
                all_docs.extend(retrieve(
                    f"service {svc} dependencies impact",
                    n_results=1, doc_type="service",
                ))
            except Exception as exc:
                logger.warning("Service retrieval failed for %s: %s", svc, exc)

    if affected_services:
        incident_query = f"past incident affecting {' '.join(affected_services[:3])}"
        try:
            all_docs.extend(retrieve(incident_query, n_results=3, doc_type="incident"))
        except Exception as exc:
            logger.warning("Incident retrieval failed: %s", exc)

    if affected_services:
        biz_query = f"business impact of {' '.join(affected_services[:3])}"
        try:
            all_docs.extend(retrieve(biz_query, n_results=3, doc_type="business"))
        except Exception as exc:
            logger.warning("Business retrieval failed: %s", exc)

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for doc in all_docs:
        if doc["id"] not in seen:
            seen.add(doc["id"])
            unique.append(doc)

    unique = unique[:max_docs]
    if not unique:
        return ""

    parts: list[str] = []
    for doc in unique:
        doc_type = doc.get("metadata", {}).get("type", "general")
        header = f"[{doc_type.upper()}] {doc['id']}"
        parts.append(f"{header}\n{doc['text']}")

    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Demo-response fast-path
# ---------------------------------------------------------------------------
_ARABIC_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670]")
_ARABIC_NORMALIZE = [
    (re.compile(r"[إأآا]"), "ا"),  # alef variants -> alef
    (re.compile(r"ى"), "ي"),       # alef maqsura -> ya
    (re.compile(r"ة"), "ه"),       # ta marbuta -> ha
    (re.compile(r"ؤ"), "و"),       # waw with hamza -> waw
    (re.compile(r"ئ"), "ي"),       # ya with hamza -> ya
    (re.compile(r"\s+"), " "),     # collapse whitespace
]


def _normalize(text: str) -> str:
    """
    Normalize a query for fuzzy string comparison.

    Steps:
        1. Lowercase.
        2. Strip Arabic diacritics (tashkeel) — no one types them.
        3. Normalize alef/ya/ta-marbuta variants — users swap them freely.
        4. Collapse whitespace.
        5. Strip trailing punctuation that has no semantic weight.

    This means "إيه الخدمات؟" and "ايه الخدمات" and "ايه  الخدمات !"
    all normalize to the same string.
    """
    if not text:
        return ""
    text = text.lower().strip()
    text = _ARABIC_DIACRITICS.sub("", text)
    for pattern, replacement in _ARABIC_NORMALIZE:
        text = pattern.sub(replacement, text)
    # Strip common trailing/leading punctuation that varies
    text = text.strip("؟?!.,؛: ")
    return text


def _exact_or_substring_match(query: str) -> str | None:
    """
    Tier 1 fast-path: normalize and compare against demo queries.

    Matches:
        - Exact normalized equality (fast, deterministic).
        - Substring in either direction (handles extra context like
          "please tell me what are the downstream dependents of...")

    Returns the pre-authored answer or None.
    """
    try:
        from rag.demo_responses import DEMO_RESPONSES
    except Exception:
        return None

    normalized_query = _normalize(query)
    if not normalized_query:
        return None

    # First pass: exact normalized match
    for entry in DEMO_RESPONSES:
        if _normalize(entry["query"]) == normalized_query:
            return entry["answer"]

    # Second pass: substring match — the demo query sits inside the
    # user's message, or vice versa. Only for reasonably long demo
    # queries (>= 20 chars) to avoid false positives.
    for entry in DEMO_RESPONSES:
        demo_norm = _normalize(entry["query"])
        if len(demo_norm) < 20:
            continue
        if demo_norm in normalized_query or normalized_query in demo_norm:
            return entry["answer"]

    return None


def check_demo_response(query: str, threshold: float = 0.5) -> str | None:
    """
    Check if the query matches a pre-authored demo response.

    Two-tier lookup:
        Tier 1 — normalized exact / substring match. Sub-millisecond.
                 No embedding model, no ChromaDB, no network.
        Tier 2 — semantic search via ChromaDB (needs embedding model,
                 ~0.3s when warm). Used only when Tier 1 misses.

    Returns the pre-authored answer, or None to let the caller run the
    normal tool-calling flow.
    """
    if not query or not query.strip():
        return None

    # ---- Tier 1: string match (instant) --------------------------------
    answer = _exact_or_substring_match(query)
    if answer:
        logger.info("Demo fast-path HIT (string match)")
        return answer

    # ---- Tier 2: semantic search (fallback) ----------------------------
    try:
        results = search_similar(query, n_results=1)
    except Exception as exc:
        logger.warning("check_demo_response: search_similar failed: %s", exc)
        return None

    ids = (results.get("ids") or [[]])[0]
    metas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    if not ids:
        return None

    metadata = metas[0] if metas else {}
    distance = distances[0] if distances else None

    if not isinstance(metadata, dict):
        return None

    answer = metadata.get("answer")
    if not answer:
        return None

    if distance is None or distance > threshold:
        return None

    logger.info("Demo fast-path HIT (semantic match, distance=%.3f)", distance)
    return answer


__all__ = ["build_context", "retrieve", "check_demo_response"]