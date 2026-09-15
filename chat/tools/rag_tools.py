"""
rag_tools.py — Retrieval-Augmented Generation tools for the agent.

This is a STUB for now. The real RAG system (ChromaDB + OpenAI embeddings)
is built on Day 3. This stub returns a clear "not yet available" message
so the agent does not hallucinate when asked about the knowledge base.

Public API:
    search_knowledge_base — placeholder for the real RAG query.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool


logger = logging.getLogger(__name__)


@tool
def search_knowledge_base(query: str) -> str:
    """
    Search the project knowledge base for relevant context.

    Use this when the user asks about documented incidents, service
    descriptions, past post-mortems, or any information that is NOT in
    the dependency graph or the analysis database.

    Args:
        query: A natural-language search query.
               Example: "why did the checkout service fail last month?"

    Returns:
        Relevant context from the knowledge base, or a message indicating
        the knowledge base is not yet available.
    """
    logger.info("search_knowledge_base called (stub): %s", query)
    return (
        "The knowledge base is not yet available in this build. "
        "Please rely on the dependency graph and analysis history tools "
        "for now. RAG integration is planned for a future release."
    )


__all__ = ["search_knowledge_base"]