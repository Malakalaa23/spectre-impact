"""Populate the RAG knowledge base from Spectre's curated maps and source files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from rag.vector_store import VectorStore


def _chunks(text: str, size: int = 1800) -> list[str]:
    lines = text.splitlines()
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for line in lines:
        if current and length + len(line) + 1 > size:
            chunks.append("\n".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks or [text]


def enrich_repository(repository_root: str | Path = ".", store: VectorStore | None = None, *, target_docs: int = 0) -> int:
    root = Path(repository_root).resolve()
    store = store or VectorStore()
    data_dir = Path(__file__).resolve().parents[1] / "backend" / "data"
    if not data_dir.exists():
        data_dir = root / "backend" / "data"

    count = 0
    # Service/business knowledge.
    graph_path = data_dir / "dependency_graph.yaml"
    business_path = data_dir / "business_map.yaml"
    if graph_path.exists():
        graph = yaml.safe_load(graph_path.read_text(encoding="utf-8")) or {}
        for name, node in graph.get("nodes", {}).items():
            business = {}
            if business_path.exists():
                business = (yaml.safe_load(business_path.read_text(encoding="utf-8")) or {}).get(name, {})
            text = (
                f"Component: {name}\nType: {node.get('type')}\nOwner: {node.get('owner')}\n"
                f"Criticality: {node.get('criticality')}\nDepends-on impact children: {', '.join(node.get('children', [])) or 'none'}\n"
                f"Feature: {business.get('feature', 'unknown')}\nUsers potentially affected: {business.get('users_percentage', 0)}%"
            )
            store.add(f"component:{name}", text, {"component": name, "owner": node.get("owner", "unknown"), "doc_type": "component"})
            count += 1

    # Repository source chunks become retrieval context for code questions.
    skipped = {".git", ".venv", "venv", "node_modules", "__pycache__", ".spectre", ".pytest_cache"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".js", ".jsx", ".ts", ".tsx", ".yaml", ".yml", ".json", ".md", ".tf"}:
            continue
        if any(part in skipped for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for idx, chunk in enumerate(_chunks(text)):
            digest = hashlib.sha256(f"{path}:{idx}:{chunk}".encode()).hexdigest()[:16]
            store.add(f"source:{digest}", f"File: {path.relative_to(root)}\n\n{chunk}", {"path": str(path.relative_to(root)), "doc_type": "source"})
            count += 1

    # Optional deterministic synthetic runbook records make the CLI useful on a
    # small demo repository without pretending they came from production data.
    if target_docs and count < target_docs:
        graph = yaml.safe_load(graph_path.read_text(encoding="utf-8")) if graph_path.exists() else {"nodes": {}}
        nodes = list((graph or {}).get("nodes", {})) or ["application"]
        idx = 0
        while count < target_docs:
            component = nodes[idx % len(nodes)]
            scenario = ["deployment", "rollback", "incident", "validation", "ownership"][idx % 5]
            text = (
                f"Synthetic demo runbook record {idx + 1}. Component {component}. Scenario {scenario}. "
                "This record is generated from the curated Spectre dependency map and must not be treated as a real incident report."
            )
            store.add(f"synthetic:{idx}", text, {"component": component, "scenario": scenario, "doc_type": "synthetic_demo"})
            count += 1
            idx += 1
    return count


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", nargs="?", default=".")
    parser.add_argument("--target-docs", type=int, default=0)
    args = parser.parse_args()
    print(f"Indexed {enrich_repository(args.repository, target_docs=args.target_docs)} documents")
