"""
bfs_tools.py — Tools that expose the Spectre Impact BFS engine to the agent.

These tools let Lya answer questions like:
    - "What happens if I change terraform/customer_database.tf?"
    - "Which services are in the dependency graph?"

Robustness note:
    The `analyze_blast_radius` tool accepts partial file paths. If the
    caller (or the LLM) passes `customer_database.tf` without the
    `terraform/` prefix, the tool tries to resolve it against the
    resource map before failing. This makes the tool resilient to how
    the LLM extracts file names from natural language.

Public API:
    analyze_blast_radius  — BFS blast radius for a set of changed files.
    list_services         — list every node in the dependency graph.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_core.tools import tool

from backend.analysis.change_analysis_engine import analyze_impact
from backend.analysis.dependency_graph import DependencyGraph


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = PROJECT_ROOT / "backend" / "data" / "dependency_graph.yaml"
RESOURCE_MAP_PATH = PROJECT_ROOT / "backend" / "data" / "resource_map.json"


# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------
def _load_resource_map() -> dict[str, list[str]]:
    """
    Load the file → resource mapping. Cached after first read.

    Returns:
        A dict mapping file paths (e.g. "terraform/customer_database.tf")
        to lists of resource names (e.g. ["customer_database"]).
    """
    if not RESOURCE_MAP_PATH.exists():
        return {}
    try:
        with open(RESOURCE_MAP_PATH, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not load resource map: %s", exc)
        return {}


def _resolve_file(raw: str, resource_map: dict[str, list[str]]) -> str:
    """
    Try to resolve a user-supplied file path to a resource_map key.

    Resolution order:
        1. Exact match.
        2. Match with forward slashes (normalize \\ → /).
        3. Strip leading "./".
        4. Match by basename (e.g. "customer_database.tf" → find any key ending
           with "/customer_database.tf" or equal to it).
        5. If nothing matches, return the original string so the tool can
           report it as unknown.

    Args:
        raw: The raw file path string.
        resource_map: The loaded file → resource mapping.

    Returns:
        A file path (hopefully a key in resource_map), or the original
        string if no resolution was possible.
    """
    if not raw:
        return raw

    # Normalize backslashes
    candidate = raw.strip().replace("\\", "/")

    # Strip leading ./
    if candidate.startswith("./"):
        candidate = candidate[2:]

    # 1. Exact match
    if candidate in resource_map:
        return candidate

    # 2. Try appending common prefixes
    for prefix in ("terraform/", "services/", "apis/", "frontend/"):
        prefixed = f"{prefix}{candidate}"
        if prefixed in resource_map:
            return prefixed

    # 3. Try matching by basename
    basename = candidate.split("/")[-1]
    for key in resource_map:
        if key.split("/")[-1] == basename:
            return key

    # 4. Try matching by filename without extension
    stem = basename.rsplit(".", 1)[0]
    for key in resource_map:
        key_stem = key.split("/")[-1].rsplit(".", 1)[0]
        if key_stem == stem:
            return key

    # No resolution found — return original
    return raw


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

    The tool is tolerant of partial paths. You may pass a bare filename
    (e.g. "customer_database.tf") and it will try to resolve it against
    the project's resource map.

    Args:
        changed_files: A comma-separated list of file paths.
                       Example: "terraform/customer_database.tf"
                       Example: "services/payment/app.py, apis/checkout.py"
                       Example: "customer_database.tf"  (bare filename works)

    Returns:
        A human-readable summary of the blast radius: changed resource(s),
        affected services, business impact percentage, and evidence paths.
    """
    # Parse the comma-separated input
    raw_files = [f.strip() for f in changed_files.split(",") if f.strip()]
    if not raw_files:
        return "No files provided. Please pass one or more file paths."

    # Resolve each raw file to a resource_map key when possible
    resource_map = _load_resource_map()
    resolved_files = [_resolve_file(f, resource_map) for f in raw_files]

    if resolved_files != raw_files:
        logger.info("Resolved files: %r → %r", raw_files, resolved_files)

    try:
        result = analyze_impact(resolved_files)
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

    for service in affected[:20]:
        lines.append(f"  - {service}")
    if len(affected) > 20:
        lines.append(f"  ... and {len(affected) - 20} more")

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