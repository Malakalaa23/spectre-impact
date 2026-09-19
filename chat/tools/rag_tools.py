"""
rag_tools.py — RAG tool for the Lya chat agent.

Exposes the ChromaDB knowledge base to Lya as a LangChain tool.
Lya can search for past incidents, service documentation, and business
impact information to ground her answers.

Public API:
    search_knowledge_base — the tool function.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool


logger = logging.getLogger(__name__)


@tool
def search_knowledge_base(query: str) -> str:
    """
    Search the Spectre Impact knowledge base for relevant context.

    Use this when the user asks about:
        - Past incidents affecting a service
        - Service ownership or criticality
        - Business impact of a service
        - Historical PR analyses
        - Any information NOT in the dependency graph or current analysis

    Args:
        query: A natural-language search query.
               Example: "past incidents affecting payment_service"
               Example: "who owns the checkout API?"
               Example: "what happened in PR #445?"

    Returns:
        Relevant context chunks from the knowledge base, or a message
        indicating nothing was found.
    """
    try:
        from rag.retriever import build_context
    except ImportError as exc:
        logger.warning("RAG retriever unavailable: %s", exc)
        return "The knowledge base is not yet available in this build."

    if not query or not query.strip():
        return "Please provide a search query."

    try:
        context = build_context(query=query, max_docs=6)
    except Exception as exc:  # noqa: BLE001
        logger.exception("RAG retrieval failed")
        return f"Knowledge base search failed: {exc}"

    if not context.strip():
        return f"No relevant information found for: {query}"

    return context


__all__ = ["search_knowledge_base"]