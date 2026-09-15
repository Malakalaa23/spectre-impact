"""
rebuild_graph.py — Rebuild dependency_graph.yaml from the PNG topology.

The original YAML was overwritten with a stub. This script writes the
correct version in the `nodes:` dict schema that DependencyGraph expects.

Sources of truth:
    - dependency_graph.png (visual map, checked into repo)
    - dependency_graph.json (frontend/journey/business slice)
    - current dependency_graph.yaml stub (infra tier edges)

Output:
    backend/data/dependency_graph.yaml   (overwrites the stub)

Backup:
    backend/data/dependency_graph.yaml.bak   (original stub preserved)

Run:
    python rebuild_graph.py

Then verify:
    python -m pytest backend/analysis/test_bfs.py -v
    python -m pytest backend/test_analysis_engine.py -v
"""

import io
import shutil
import sys
from pathlib import Path

import yaml


# Force UTF-8 on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
YAML_PATH = ROOT / "backend" / "data" / "dependency_graph.yaml"
BACKUP_PATH = ROOT / "backend" / "data" / "dependency_graph.yaml.bak"


# ---------------------------------------------------------------------------
# THE COMPLETE TOPOLOGY — from the PNG
# ---------------------------------------------------------------------------
# Every node with its type, owner, criticality, and downstream children.
# This is what the full graph looks like.
# ---------------------------------------------------------------------------
GRAPH = {
    # ---- INFRA TIER ----
    "customer_database": {
        "type": "database",
        "owner": "platform-team",
        "criticality": "critical",
        "children": [
            "login_service",
            "checkout_service",
            "payment_service",
            "profile_service",
        ],
    },
    "redis_cache": {
        "type": "cache",
        "owner": "platform-team",
        "criticality": "high",
        "children": [
            "login_service",
            "profile_service",
        ],
    },

    # ---- SERVICE TIER ----
    "login_service": {
        "type": "service",
        "owner": "identity-team",
        "criticality": "critical",
        "children": [
            "login_api",
            "checkout_api",
        ],
    },
    "checkout_service": {
        "type": "service",
        "owner": "payments-team",
        "criticality": "critical",
        "children": [
            "checkout_api",
        ],
    },
    "payment_service": {
        "type": "service",
        "owner": "payments-team",
        "criticality": "critical",
        "children": [
            "checkout_api",
        ],
    },
    "profile_service": {
        "type": "service",
        "owner": "identity-team",
        "criticality": "high",
        "children": [
            "profile_api",
        ],
    },

    # ---- API TIER ----
    "login_api": {
        "type": "api",
        "owner": "identity-team",
        "criticality": "critical",
        "children": [
            "web_frontend",
            "mobile_app",
        ],
    },
    "checkout_api": {
        "type": "api",
        "owner": "payments-team",
        "criticality": "critical",
        "children": [
            "web_frontend",
            "mobile_app",
        ],
    },
    "profile_api": {
        "type": "api",
        "owner": "identity-team",
        "criticality": "high",
        "children": [
            "web_frontend",
        ],
    },

    # ---- FRONTEND TIER ----
    "web_frontend": {
        "type": "frontend",
        "owner": "frontend-team",
        "criticality": "high",
        "children": [
            "login_journey",
            "checkout_journey",
            "profile_journey",
        ],
    },
    "mobile_app": {
        "type": "mobile_app",
        "owner": "mobile-team",
        "criticality": "high",
        "children": [
            "login_journey",
            "checkout_journey",
        ],
    },

    # ---- CUSTOMER JOURNEY TIER ----
    "login_journey": {
        "type": "customer_journey",
        "owner": "product-team",
        "criticality": "critical",
        "children": [
            "customer_retention",
            "customer_satisfaction",
            "revenue_generation",
        ],
    },
    "checkout_journey": {
        "type": "customer_journey",
        "owner": "product-team",
        "criticality": "critical",
        "children": [
            "customer_retention",
            "customer_satisfaction",
            "revenue_generation",
        ],
    },
    "profile_journey": {
        "type": "customer_journey",
        "owner": "product-team",
        "criticality": "medium",
        "children": [
            "customer_retention",
            "customer_satisfaction",
            "revenue_generation",
        ],
    },

    # ---- BUSINESS TIER ----
    "customer_retention": {
        "type": "business",
        "owner": "management",
        "criticality": "high",
        "children": [],
    },
    "customer_satisfaction": {
        "type": "business",
        "owner": "management",
        "criticality": "medium",
        "children": [],
    },
    "revenue_generation": {
        "type": "business",
        "owner": "management",
        "criticality": "critical",
        "children": [],
    },
}


# ---------------------------------------------------------------------------
# VALIDATION — catch typos before writing
# ---------------------------------------------------------------------------
def validate_topology() -> None:
    """Confirm every child exists as a node, and there are no cycles."""
    all_nodes = set(GRAPH.keys())

    # Check every child exists
    for node, meta in GRAPH.items():
        for child in meta["children"]:
            if child not in all_nodes:
                raise ValueError(
                    f"Node '{node}' references unknown child '{child}'"
                )

    # Check for cycles (DFS)
    visited: set[str] = set()
    in_stack: set[str] = set()

    def dfs(node: str) -> None:
        if node in in_stack:
            raise ValueError(f"Cycle detected at node '{node}'")
        if node in visited:
            return
        visited.add(node)
        in_stack.add(node)
        for child in GRAPH[node]["children"]:
            dfs(child)
        in_stack.remove(node)

    for node in GRAPH:
        dfs(node)


# ---------------------------------------------------------------------------
# BACKUP + WRITE
# ---------------------------------------------------------------------------
def backup_existing() -> None:
    """Copy the current YAML to .bak if it exists and hasn't been backed up."""
    if YAML_PATH.exists() and not BACKUP_PATH.exists():
        shutil.copy2(YAML_PATH, BACKUP_PATH)
        print(f"  Backed up: {BACKUP_PATH.name}")
    elif BACKUP_PATH.exists():
        print(f"  Backup already exists: {BACKUP_PATH.name}")
    else:
        print(f"  No existing YAML to back up")


def write_yaml() -> None:
    """Write the rebuilt graph to dependency_graph.yaml."""
    payload = {"nodes": GRAPH}
    with open(YAML_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            payload,
            f,
            default_flow_style=False,
            sort_keys=True,
            allow_unicode=True,
        )
    print(f"  Wrote: {YAML_PATH}")
    print(f"  Nodes: {len(GRAPH)}")
    total_children = sum(len(m["children"]) for m in GRAPH.values())
    print(f"  Total edges: {total_children}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 70)
    print("  REBUILD dependency_graph.yaml")
    print("=" * 70)
    print()

    print("[1/3] Validating topology...")
    validate_topology()
    print("  ✓ No unknown children")
    print("  ✓ No cycles")
    print()

    print("[2/3] Backing up existing YAML...")
    backup_existing()
    print()

    print("[3/3] Writing new YAML...")
    write_yaml()
    print()

    print("=" * 70)
    print("  DONE")
    print("=" * 70)
    print()
    print("Next: verify with tests")
    print("  python -m pytest backend/analysis/test_bfs.py -v")
    print("  python -m pytest backend/test_analysis_engine.py -v")
    print()


if __name__ == "__main__":
    main()