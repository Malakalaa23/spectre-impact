from backend.analysis.dependency_graph import DependencyGraph
from backend.analysis.bfs import bfs, bfs_with_paths


def test_bfs_finds_all_downstream_nodes():
    graph = DependencyGraph("backend/data/dependency_graph.yaml")
    assert bfs(graph, "profile_journey") == [
        "profile_journey", "customer_satisfaction"
    ]


def test_bfs_returns_explainable_paths():
    graph = DependencyGraph("backend/data/dependency_graph.yaml")
    _, paths = bfs_with_paths(graph, "payment_service")
    assert paths["revenue_generation"] == [
        "payment_service", "checkout_api", "web_frontend",
        "checkout_journey", "revenue_generation",
    ]
