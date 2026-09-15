"""
chat.tools — Tool definitions for the Lya chat agent.

Each module in this package defines LangChain-compatible tools that the
agent can call. The tools wrap existing Spectre Impact functionality
(BFS, database, RAG) so the agent answers with real data.

Public API:
    ALL_TOOLS — the list of every tool, ready to pass to the agent.
"""

from chat.tools.bfs_tools import analyze_blast_radius, list_services
from chat.tools.db_tools import get_past_prs, get_pr_details, get_recent_incidents
from chat.tools.rag_tools import search_knowledge_base


# The full tool list, in the order we want them shown to the agent.
# Order matters only for readability — the LLM picks based on descriptions.
ALL_TOOLS = [
    analyze_blast_radius,
    list_services,
    get_past_prs,
    get_pr_details,
    get_recent_incidents,
    search_knowledge_base,
]


__all__ = ["ALL_TOOLS"]