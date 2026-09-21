"""
retriever.py — Query ChromaDB and build LLM-ready context.

Given a user query or set of affected services, this module retrieves
the most relevant documents and assembles them into a single context
string that the LLM can use as grounding.

Language handling:
    The embedding model (`ibm-granite/granite-embedding-97m-multilingual-r2`)
    is multilingual. Arabic and English queries embed into the same
    vector space as the documents, so no translation step is needed.
    Earlier versions of this module translated Arabic queries to
    English before embedding because the previous model was English-only.
    That workaround is gone — it would degrade retrieval quality now,
    since the model already understands Arabic directly.

Public API:
    retrieve(query, n_results, doc_type) -> list[dict]
    build_context(query, affected_services, max_docs) -> str
"""

from __future__ import annotations

import logging
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
    """
    Retrieve the top-K most similar documents as a list of dicts.

    Args:
        query: Natural-language search query (any supported language).
        n_results: How many docs to return.
        doc_type: Optional filter ("service", "incident", "business", "resource_map").

    Returns:
        A list of dicts: [{id, text, metadata, distance}, ...], sorted by
        distance ascending (closest first).
    """
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
    """
    Build a context string that combines relevant documents from the store.

    The context is used to ground LLM responses. It combines:
        1. Documents matching the query semantically (top 4).
        2. Documents about each affected service (up to 4).
        3. Documents about matching past incidents (top 3).
        4. Business-impact documents for the affected services (top 3).

    Duplicates are removed; the result is capped at `max_docs` chunks.

    Args:
        query: The user's question or task. Optional.
        affected_services: Optional list of service names to fetch docs for.
        max_docs: Maximum number of unique documents to include.

    Returns:
        A single string with all context chunks separated by "\n\n---\n\n".
        Returns an empty string if nothing is found.
    """
    all_docs: list[dict[str, Any]] = []

    if query and query.strip():
        try:
            query_docs = retrieve(query, n_results=4)
            all_docs.extend(query_docs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Query retrieval failed: %s", exc)

    if affected_services:
        for svc in affected_services[:4]:
            try:
                svc_docs = retrieve(
                    f"service {svc} dependencies impact",
                    n_results=1,
                    doc_type="service",
                )
                all_docs.extend(svc_docs)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Service retrieval failed for %s: %s", svc, exc)

    if affected_services:
        incident_query = f"past incident affecting {' '.join(affected_services[:3])}"
        try:
            incident_docs = retrieve(incident_query, n_results=3, doc_type="incident")
            all_docs.extend(incident_docs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Incident retrieval failed: %s", exc)

    if affected_services:
        biz_query = f"business impact of {' '.join(affected_services[:3])}"
        try:
            biz_docs = retrieve(biz_query, n_results=3, doc_type="business")
            all_docs.extend(biz_docs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Business retrieval failed: %s", exc)

    # Deduplicate by id, keeping first occurrence
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


__all__ = ["build_context", "retrieve"]