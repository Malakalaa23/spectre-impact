"""Render simple blast-radius graphs and export data for an interactive UI."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import Patch

from backend.analysis.dependency_graph import DependencyGraph
from backend.analysis.change_analysis_engine import analyze_impact


TYPE_COLORS = {
    "database": "#ef4444", "cache": "#f97316", "service": "#3b82f6",
    "api": "#8b5cf6", "frontend": "#22c55e", "mobile_app": "#14b8a6",
    "customer_journey": "#eab308", "business": "#ec4899",
}


def _load_graph() -> tuple[nx.DiGraph, dict]:
    data_path = Path(__file__).resolve().parents[1] / "data" / "dependency_graph.yaml"
    graph_data = DependencyGraph(str(data_path)).nodes
    graph = nx.DiGraph()
    for node, metadata in graph_data.items():
        graph.add_node(node, node_type=metadata["type"])
        graph.add_edges_from((node, child) for child in metadata["children"])

    for node in nx.topological_sort(graph):
        predecessors = list(graph.predecessors(node))
        graph.nodes[node]["layer"] = (
            max((graph.nodes[parent]["layer"] + 1 for parent in predecessors), default=0)
        )
    return graph, graph_data


def _tree_positions(graph: nx.DiGraph) -> dict:
    """Simple top-to-bottom tree-like positions, grouped by dependency level."""
    layers: dict[int, list[str]] = {}
    for node, data in graph.nodes(data=True):
        layers.setdefault(data["layer"], []).append(node)
    positions = {}
    for layer, nodes in layers.items():
        for index, node in enumerate(sorted(nodes)):
            positions[node] = (index - (len(nodes) - 1) / 2, -layer)
    return positions


def _render(graph: nx.DiGraph, output: Path, title: str, changed_nodes: set[str] | None = None) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    changed_nodes = changed_nodes or set()
    plt.figure(figsize=(14, 9))
    positions = _tree_positions(graph)
    colors = [TYPE_COLORS.get(graph.nodes[node]["node_type"], "#94a3b8") for node in graph.nodes]
    borders = ["#111827" if node in changed_nodes else "white" for node in graph.nodes]
    nx.draw_networkx(graph, positions, node_color=colors, edgecolors=borders,
                     linewidths=3, node_size=2100, font_size=8, font_weight="bold",
                     arrows=True, edge_color="#64748b", arrowsize=18)
    plt.title(title, fontsize=16)
    present_types = {graph.nodes[node]["node_type"] for node in graph.nodes}
    legend = [Patch(color=color, label=node_type.replace("_", " ").title())
              for node_type, color in TYPE_COLORS.items() if node_type in present_types]
    plt.legend(handles=legend, loc="upper left", title="Component type")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output, dpi=180, bbox_inches="tight")
    plt.close()
    return output


def create_dependency_graph(output_path: str | Path | None = None) -> Path:
    """Render the complete dependency map as a simple tree-style PNG."""
    graph, _ = _load_graph()
    output = Path(output_path) if output_path else Path(__file__).resolve().parents[1] / "data" / "dependency_graph.png"
    return _render(graph, output, "Spectre Impact Dependency Map")


def create_blast_radius_graph(changed_files: list[str], output_path: str | Path | None = None) -> Path:
    """Render only the components affected by a single pull request."""
    analysis = analyze_impact(changed_files)
    graph, _ = _load_graph()
    affected = set(analysis["affected_services"])
    subgraph = graph.subgraph(affected).copy()
    output = Path(output_path) if output_path else Path(__file__).resolve().parents[1] / "data" / "blast_radius.png"
    label = ", ".join(analysis["changed_resources"]) or "unknown files"
    return _render(subgraph, output, f"PR Blast Radius: {label}", set(analysis["changed_resources"]))


def export_graph_json(output_path: str | Path | None = None, changed_files: list[str] | None = None) -> Path:
    """Export nodes and directed links for a frontend graph library."""
    graph, graph_data = _load_graph()
    analysis = analyze_impact(changed_files) if changed_files is not None else None
    included = set(analysis["affected_services"]) if analysis else set(graph.nodes)
    nodes = [
        {"id": node, **graph_data[node], "impacted": bool(analysis),
         "changed": bool(analysis and node in analysis["changed_resources"])}
        for node in sorted(included)
    ]
    links = [{"source": source, "target": target}
             for source, target in graph.edges if source in included and target in included]
    payload = {"nodes": nodes, "links": links, "analysis": analysis}
    output = Path(output_path) if output_path else Path(__file__).resolve().parents[1] / "data" / "dependency_graph.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    print(create_dependency_graph())
