"""
bfs_tools.py — Tools that expose the Spectre Impact BFS engine to the agent.

These tools let Lya answer questions like:
    - "What happens if I change terraform/customer_database.tf?"
    - "Which services are in the dependency graph?"

Both tools wrap existing, tested functionality:
    - analyze_impact()          from backend.analysis.change_analysis_engine
    - DependencyGraph           from backend.analysis.dependency_graph
"""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_core.tools import tool

from backend.analysis.change_analysis_engine import analyze_impact
from backend.analysis.dependency_graph import DependencyGraph


logger = logging.getLogger(__name__)


# Where the graph lives — resolved relative to the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = PROJECT_ROOT / "backend" / "data" / "dependency_graph.yaml"


# ---------------------------------------------------------------------------
# Tool 1: analyze_blast_radius
# ---------------------------------------------------------------------------
@tool
def analyze_blast_radius(changed_files: str) -> str:
    """
    Analyze which services are affected by changing one or more files.

    Use this when the user asks what a change will impact — for example:
        "What happens if I change terraform/customer_database.tf?"
        "Which services are affected by modifying services/payment/app.py?"

    Args:
        changed_files: A comma-separated list of file paths.
                       Example: "terraform/customer_database.tf"
                       Example: "services/payment/app.py, apis/checkout.py"

    Returns:
        A human-readable summary of the blast radius:
        changed resource(s), affected services, business impact percentage,
        and the evidence paths BFS used to reach them.
    """
    # Parse the comma-separated input into a clean list
    files = [f.strip() for f in changed_files.split(",") if f.strip()]
    if not files:
        return "No files provided. Please pass one or more file paths."

    try:
        result = analyze_impact(files)
    except Exception as exc:  # noqa: BLE001
        logger.exception("analyze_blast_radius failed")
        return f"Analysis failed: {exc}"

    # Build a clean, LLM-friendly summary
    changed = result.get("changed_resources") or [result.get("changed_resource", "unknown")]
    affected = result.get("affected_services") or []
    impact = result.get("business_impact", 0)
    unknown = result.get("unknown_resources") or []
    evidence = result.get("evidence") or []

    lines: list[str] = []
    lines.append(f"Changed resource(s): {', '.join(changed)}")
    lines.append(f"Business impact: {impact}%")
    lines.append(f"Affected services ({len(affected)}):")

    # Show up to 20 services to keep the response readable
    for service in affected[:20]:
        lines.append(f"  - {service}")
    if len(affected) > 20:
        lines.append(f"  ... and {len(affected) - 20} more")

    # Include a few evidence paths so the agent can cite them
    if evidence:
        lines.append("")
        lines.append(f"Evidence paths ({len(evidence)} total, showing up to 5):")
        for path in evidence[:5]:
            lines.append(f"  - {' → '.join(path)}")

    if unknown:
        lines.append("")
        lines.append(f"Unknown files (not in resource map): {', '.join(unknown)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 2: list_services
# ---------------------------------------------------------------------------
@tool
def list_services() -> str:
    """
    List every service, API, frontend, journey, and business node in the
    dependency graph, grouped by type.

    Use this when the user asks:
        "What services are in the system?"
        "List all the components."
        "What services does Spectre Impact track?"
    """
    try:
        graph = DependencyGraph(str(GRAPH_PATH))
    except Exception as exc:  # noqa: BLE001
        logger.exception("list_services failed")
        return f"Could not load dependency graph: {exc}"

    # Group nodes by type for a clean display
    by_type: dict[str, list[str]] = {}
    for node_name, meta in graph.nodes.items():
        node_type = meta.get("type", "unknown")
        by_type.setdefault(node_type, []).append(node_name)

    lines = [f"Total nodes: {len(graph.nodes)}"]
    for node_type in sorted(by_type.keys()):
        names = sorted(by_type[node_type])
        lines.append(f"\n{node_type} ({len(names)}):")
        for name in names:
            lines.append(f"  - {name}")

    return "\n".join(lines)


__all__ = ["analyze_blast_radius", "list_services"]