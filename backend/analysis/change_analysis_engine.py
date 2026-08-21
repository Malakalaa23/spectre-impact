from pathlib import Path

import yaml

from backend.models.analysis_result import AnalysisResult
from backend.detector.resource_detector import ResourceDetector
from backend.analysis.dependency_graph import DependencyGraph
from backend.analysis.bfs import bfs_with_paths
from backend.analysis.risk_rules import RiskRules


class ChangeAnalysisEngine:
    """
    Connects the resource detector, dependency graph,
    BFS, risk rules, and AnalysisResult.
    """

    def __init__(
        self,
        resource_map_path: str,
        dependency_graph_path: str,
        business_map_path: str | None = None,
    ):
        # Load the file -> resource mapping
        self.resource_detector = ResourceDetector(
            resource_map_path
        )

        # Load the dependency graph
        self.graph = DependencyGraph(
            dependency_graph_path
        )

        # Load deterministic risk rules
        self.risk_rules = RiskRules()
        self.business_map = self._load_business_map(business_map_path)

    @staticmethod
    def _load_business_map(path: str | None) -> dict:
        if path is None:
            path = str(Path(__file__).resolve().parents[1] / "data" / "business_map.yaml")
        with open(path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}

    def analyze_change(self, pull_request):
        """
        Takes a parsed PullRequestEvent and returns
        an AnalysisResult.
        """

        # ---------------------------------------------
        # 1. Get files changed by the PR
        # ---------------------------------------------

        changed_files = pull_request.changed_files

        # ---------------------------------------------
        # 2. Convert changed files into graph resources
        # ---------------------------------------------

        detection = self.resource_detector.detect_resources(
            changed_files
        )

        changed_resources = detection.detected_resources
        unknown_resources = detection.unknown_resources

        # ---------------------------------------------
        # 3. Run BFS for every changed resource
        # ---------------------------------------------

        affected_nodes = set()
        evidence_by_node: dict[str, list[str]] = {}

        for resource in changed_resources:

            affected, paths = bfs_with_paths(
                self.graph,
                resource
            )

            # A set automatically removes duplicates
            affected_nodes.update(affected)
            for node, path in paths.items():
                evidence_by_node.setdefault(node, path)

        # ---------------------------------------------
        # 4. Categorize affected nodes by type
        # ---------------------------------------------

        affected_databases = []
        affected_services = []
        affected_apis = []
        affected_frontends = []
        affected_customer_journeys = []
        affected_business_capabilities = []

        for node_name in affected_nodes:

            # Get information about this node
            node = self.graph.get_node(node_name)

            # Skip missing nodes
            if node is None:
                continue

            node_type = node["type"]

            # Put the node into the correct category
            if node_type == "database":
                affected_databases.append(node_name)

            elif node_type == "service":
                affected_services.append(node_name)

            elif node_type == "api":
                affected_apis.append(node_name)

            elif node_type in ["frontend", "mobile_app"]:
                affected_frontends.append(node_name)

            elif node_type == "customer_journey":
                affected_customer_journeys.append(node_name)

            elif node_type == "business":
                affected_business_capabilities.append(
                    node_name
                )

        # ---------------------------------------------
        # 5. Sort results for consistent output
        # ---------------------------------------------

        affected_databases.sort()
        affected_services.sort()
        affected_apis.sort()
        affected_frontends.sort()
        affected_customer_journeys.sort()
        affected_business_capabilities.sort()

        # ---------------------------------------------
        # 6. Create the initial analysis result
        # ---------------------------------------------

        result = AnalysisResult(

            changed_files=changed_files,

            changed_resources=changed_resources,

            unknown_resources=unknown_resources,

            affected_databases=affected_databases,

            affected_services=affected_services,

            affected_apis=affected_apis,

            affected_frontends=affected_frontends,

            affected_customer_journeys=(
                affected_customer_journeys
            ),

            affected_business_capabilities=(
                affected_business_capabilities
            ),

            # Worst-case percentage from the configurable business map.
            business_impact=max(
                (self.business_map.get(node, {}).get("users_percentage", 0)
                 for node in affected_nodes),
                default=0,
            ),
            severity="LOW",
            confidence=100,
            deployment_strategy="Rolling",
            rollback_required=False,

            # Evidence will be implemented later
            evidence=[evidence_by_node[node] for node in sorted(evidence_by_node)]
        )

        # ---------------------------------------------
        # 7. Apply deterministic risk rules
        # ---------------------------------------------

        result = self.risk_rules.apply(result)

        return result


def analyze_impact(changed_files: list[str]) -> dict:
    """Integration contract for the webhook backend.

    Returns a compact, JSON-ready result without requiring a GitHub event or
    either teammate's module.
    """
    data_dir = Path(__file__).resolve().parents[1] / "data"
    engine = ChangeAnalysisEngine(
        str(data_dir / "resource_map.json"),
        str(data_dir / "dependency_graph.yaml"),
        str(data_dir / "business_map.yaml"),
    )

    from backend.models.pull_request import PullRequestEvent
    pull_request = PullRequestEvent(
        action="opened", repository_name="unknown", pr_number=0, title="",
        body="", author="", head_branch="", base_branch="", created_at="",
        updated_at="", html_url="", changed_files=changed_files,
    )
    result = engine.analyze_change(pull_request)
    affected_nodes = sorted({node for path in result.evidence for node in path})
    return {
        "changed_resource": result.changed_resources[0] if result.changed_resources else "unknown",
        "changed_resources": result.changed_resources,
        "affected_services": affected_nodes,
        "business_impact": result.business_impact,
        "unknown_resources": result.unknown_resources,
        "evidence": result.evidence,
    }
