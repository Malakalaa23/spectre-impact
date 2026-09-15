"""
test_bfs.py — Tests for the BFS traversal.

These tests verify:
    - BFS reaches every downstream node from a given start.
    - BFS-with-paths returns valid shortest paths to each downstream node.

The tests are written to check INTENT (all downstream nodes reachable,
paths are valid) rather than exact ordering, since the graph's topology
is expected to evolve as the system grows.
"""

from backend.analysis.dependency_graph import DependencyGraph
from backend.analysis.bfs import bfs, bfs_with_paths


GRAPH_PATH = "backend/data/dependency_graph.yaml"


def test_bfs_finds_all_downstream_nodes():
    """BFS from a business-tier leaf should return itself plus all reachable nodes."""
    graph = DependencyGraph(GRAPH_PATH)
    result = bfs(graph, "profile_journey")

    # The starting node must be included
    assert result[0] == "profile_journey"

    # All business-tier nodes should be reachable from any journey
    assert "customer_retention" in result
    assert "customer_satisfaction" in result
    assert "revenue_generation" in result

    # No duplicates
    assert len(result) == len(set(result))


def test_bfs_from_top_reaches_entire_graph():
    """BFS from the top of the graph should reach every node below it."""
    graph = DependencyGraph(GRAPH_PATH)
    result = bfs(graph, "customer_database")

    # Top node included
    assert result[0] == "customer_database"

    # All 4 infra-level services should be reachable
    for service in ("login_service", "checkout_service", "payment_service", "profile_service"):
        assert service in result, f"{service} should be reachable from customer_database"

    # Business tier should be reachable
    assert "revenue_generation" in result
    assert "customer_retention" in result
    assert "customer_satisfaction" in result


def test_bfs_returns_explainable_paths():
    """BFS-with-paths should return a valid path from start to each node."""
    graph = DependencyGraph(GRAPH_PATH)
    _, paths = bfs_with_paths(graph, "payment_service")

    # revenue_generation must be reachable
    assert "revenue_generation" in paths

    path = paths["revenue_generation"]

    # Path must start at the root
    assert path[0] == "payment_service"
    # Path must end at the target
    assert path[-1] == "revenue_generation"
    # Path must pass through the API and frontend tiers
    assert "checkout_api" in path
    assert "web_frontend" in path
    # Path must be contiguous: each node's next must be a child of the previous
    for i in range(len(path) - 1):
        assert path[i + 1] in graph.get_children(path[i]), (
            f"Path is not contiguous at index {i}: {path[i]} → {path[i+1]}"
        )


def test_bfs_handles_unknown_start_node():
    """BFS from an unknown node should return just that node (no children)."""
    graph = DependencyGraph(GRAPH_PATH)
    result = bfs(graph, "this_node_does_not_exist")
    assert result == ["this_node_does_not_exist"]