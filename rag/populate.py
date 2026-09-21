"""
populate.py — Load Spectre Impact knowledge into ChromaDB.

Reads from:
    - backend/data/dependency_graph.yaml   → service documents
    - backend/data/business_map.yaml       → business impact documents
    - backend/data/resource_map.json       → file→resource mapping documents
    - history.db (analyses + commit_analyses) → past incident documents

Writes to:
    - ChromaDB collection "spectre_knowledge"

Public API:
    add_single_document(doc_id, text, metadata, doc_type) -> bool
        Add one document without resetting the collection.
        Used by the learning loop to grow the knowledge base.

    populate(reset=False, dry_run=False)
        Load all knowledge sources. Optionally resets first.

Usage:
    python -m rag.populate --reset
    python -m rag.populate
    python -m rag.populate --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.vector_store import (  # noqa: E402
    add_documents_batch,
    collection_stats,
    reset_collection,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


DATA_DIR = ROOT / "backend" / "data"
HISTORY_DB = ROOT / "history.db"


# ===========================================================================
# Learning loop — single-document addition
# ===========================================================================
def add_single_document(
    doc_id: str,
    text: str,
    metadata: dict | None = None,
    doc_type: str = "general",
) -> bool:
    """
    Add a single document to the RAG collection without resetting it.

    Used for the learning loop — every new incident or analysis gets added
    to the knowledge base so future queries have more context to draw from.

    Args:
        doc_id:   Unique identifier (e.g., "inc_pr_5_1726500000").
        text:     Document text.
        metadata: Optional metadata dict.
        doc_type: Category ("incident", "service", "business", etc.).

    Returns:
        True if added, False if the doc already exists or addition failed.
    """
    from rag.vector_store import get_collection, get_embedding

    if not doc_id or not text:
        logger.warning("add_single_document: empty doc_id or text")
        return False

    try:
        collection = get_collection()
    except Exception as exc:
        logger.warning("add_single_document: could not open collection: %s", exc)
        return False

    # Skip if the document already exists
    try:
        existing = collection.get(ids=[doc_id])
        if existing and existing.get("ids"):
            logger.info("Doc %s already exists — skipping", doc_id)
            return False
    except Exception:
        pass

    try:
        embedding = get_embedding(text)
        meta = dict(metadata or {})
        meta["type"] = doc_type

        collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[meta],
        )
        logger.info("Added single doc %s (type=%s)", doc_id, doc_type)
        return True
    except Exception as exc:
        logger.warning("Failed to add single doc %s: %s", doc_id, exc)
        return False


# ===========================================================================
# Bulk document builders
# ===========================================================================
def build_service_docs() -> tuple[list[str], list[str], list[dict], list[str]]:
    """Build documents from dependency_graph.yaml."""
    path = DATA_DIR / "dependency_graph.yaml"
    if not path.exists():
        logger.warning("dependency_graph.yaml not found — skipping service docs")
        return [], [], [], []

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    nodes = data.get("nodes", {})
    ids, texts, metas, types = [], [], [], []

    for node_name, node in nodes.items():
        node_type = node.get("type", "unknown")
        owner = node.get("owner", "unknown")
        criticality = node.get("criticality", "unknown")
        children = node.get("children", [])

        lines = [
            f"Service: {node_name}",
            f"Type: {node_type}",
            f"Owner: {owner}",
            f"Criticality: {criticality}",
        ]
        if children:
            lines.append(f"Downstream dependents: {', '.join(children)}")
            lines.append(
                f"Impact: if {node_name} changes or fails, the following "
                f"components are affected downstream: {', '.join(children)}."
            )
        else:
            lines.append(
                f"Impact: {node_name} is a leaf node — it has no downstream "
                f"dependents. Changes here do not propagate."
            )

        text = "\n".join(lines)
        ids.append(f"svc_{node_name}")
        texts.append(text)
        metas.append({
            "service": node_name,
            "node_type": node_type,
            "owner": owner,
            "criticality": criticality,
            "children": ",".join(children),
        })
        types.append("service")

    logger.info("Built %d service documents", len(ids))
    return ids, texts, metas, types


def build_business_docs() -> tuple[list[str], list[str], list[dict], list[str]]:
    """Build documents from business_map.yaml."""
    path = DATA_DIR / "business_map.yaml"
    if not path.exists():
        logger.warning("business_map.yaml not found — skipping business docs")
        return [], [], [], []

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    ids, texts, metas, types = [], [], [], []

    for service, info in data.items():
        feature = info.get("feature", "unknown feature")
        users_pct = info.get("users_percentage", 0)

        text = (
            f"Business impact of {service}\n"
            f"Feature: {feature}\n"
            f"Users affected: {users_pct}%\n"
            f"Meaning: if {service} is impacted, approximately {users_pct}% "
            f"of users experience degraded or broken functionality in {feature}."
        )

        ids.append(f"biz_{service}")
        texts.append(text)
        metas.append({
            "service": service,
            "feature": feature,
            "users_percentage": users_pct,
        })
        types.append("business")

    logger.info("Built %d business documents", len(ids))
    return ids, texts, metas, types


def build_resource_map_docs() -> tuple[list[str], list[str], list[dict], list[str]]:
    """Build documents from resource_map.json (file → resource mappings)."""
    path = DATA_DIR / "resource_map.json"
    if not path.exists():
        logger.warning("resource_map.json not found — skipping resource docs")
        return [], [], [], []

    with open(path, encoding="utf-8") as f:
        data = json.load(f) or {}

    ids, texts, metas, types = [], [], [], []

    by_resource: dict[str, list[str]] = {}
    for file_path, resource in data.items():
        by_resource.setdefault(resource, []).append(file_path)

    for resource, files in by_resource.items():
        text = (
            f"Files mapped to {resource}\n"
            f"The following files belong to the resource '{resource}':\n"
            + "\n".join(f"- {f}" for f in sorted(files))
            + f"\n\nChanges to any of these files will trigger analysis of {resource}."
        )

        ids.append(f"map_{resource}")
        texts.append(text)
        metas.append({"resource": resource, "file_count": len(files)})
        types.append("resource_map")

    logger.info("Built %d resource-map documents", len(ids))
    return ids, texts, metas, types


def build_incident_docs() -> tuple[list[str], list[str], list[dict], list[str]]:
    """Build documents from history.db (analyses + commit_analyses)."""
    if not HISTORY_DB.exists():
        logger.warning("history.db not found — skipping incident docs")
        return [], [], [], []

    ids, texts, metas, types = [], [], [], []

    try:
        conn = sqlite3.connect(str(HISTORY_DB))
        conn.row_factory = sqlite3.Row

        try:
            rows = conn.execute(
                "SELECT id, pr_number, repo_name, changed_resource, "
                "affected_services, business_impact, severity, "
                "simulation, created_at FROM analyses LIMIT 500"
            ).fetchall()

            for row in rows:
                pr = row["pr_number"]
                severity = row["severity"] or "unknown"
                resource = row["changed_resource"] or "unknown"
                impact = row["business_impact"] or 0
                created = row["created_at"] or ""
                repo = row["repo_name"] or "unknown"

                affected = _parse_list(row["affected_services"])
                sim = (row["simulation"] or "")[:400]

                text = (
                    f"Past incident: PR #{pr} in {repo}\n"
                    f"Severity: {severity}\n"
                    f"Changed resource: {resource}\n"
                    f"Business impact: {impact}%\n"
                    f"Affected services: {', '.join(affected[:15])}\n"
                    f"Occurred: {created}\n"
                )
                if sim:
                    text += f"Summary: {sim}"

                ids.append(f"inc_pr_{row['id']}")
                texts.append(text)
                metas.append({
                    "pr_number": pr,
                    "repo": repo,
                    "severity": severity,
                    "resource": resource,
                    "business_impact": impact,
                })
                types.append("incident")
        except sqlite3.OperationalError as exc:
            logger.warning("Could not read analyses table: %s", exc)

        try:
            rows = conn.execute(
                "SELECT id, commit_sha, repo_name, branch, changed_files, "
                "affected_services, business_impact, created_at "
                "FROM commit_analyses LIMIT 500"
            ).fetchall()

            for row in rows:
                sha = (row["commit_sha"] or "")[:10]
                repo = row["repo_name"] or "unknown"
                branch = row["branch"] or "unknown"
                impact = row["business_impact"] or 0
                created = row["created_at"] or ""
                affected = _parse_list(row["affected_services"])

                text = (
                    f"Past commit analysis: {sha} on {branch}\n"
                    f"Repository: {repo}\n"
                    f"Business impact: {impact}%\n"
                    f"Affected services: {', '.join(affected[:15])}\n"
                    f"Analyzed: {created}"
                )

                ids.append(f"inc_commit_{row['id']}")
                texts.append(text)
                metas.append({
                    "commit_sha": sha,
                    "repo": repo,
                    "branch": branch,
                    "business_impact": impact,
                })
                types.append("incident")
        except sqlite3.OperationalError as exc:
            logger.warning("Could not read commit_analyses table: %s", exc)

        conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to read history.db: %s", exc)

    logger.info("Built %d incident documents", len(ids))
    return ids, texts, metas, types


def _parse_list(value: Any) -> list[str]:
    """Parse a JSON-encoded list from SQLite, or split a comma string."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return [s.strip() for s in value.split(",") if s.strip()]
    return []


def populate(reset: bool = False, dry_run: bool = False) -> None:
    """Load all knowledge sources into ChromaDB."""
    if reset and not dry_run:
        logger.info("Resetting collection...")
        reset_collection()

    all_ids: list[str] = []
    all_texts: list[str] = []
    all_metas: list[dict] = []
    all_types: list[str] = []

    for builder in (
        build_service_docs,
        build_business_docs,
        build_resource_map_docs,
        build_incident_docs,
    ):
        ids, texts, metas, types = builder()
        all_ids.extend(ids)
        all_texts.extend(texts)
        all_metas.extend(metas)
        all_types.extend(types)

    logger.info("=" * 60)
    logger.info("TOTAL documents to add: %d", len(all_ids))
    logger.info("=" * 60)

    if dry_run:
        for i, (doc_id, text) in enumerate(zip(all_ids, all_texts)):
            preview = text[:120].replace("\n", " | ")
            logger.info("[%d] %s → %s", i + 1, doc_id, preview)
        logger.info("Dry run — no documents were added")
        return

    if not all_ids:
        logger.warning("No documents to add")
        return

    added = add_documents_batch(
        doc_ids=all_ids,
        texts=all_texts,
        metadatas=all_metas,
        doc_types=all_types,
    )
    logger.info("Added %d documents", added)

    stats = collection_stats()
    logger.info("Collection stats: %s", stats)


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate the RAG collection.")
    parser.add_argument("--reset", action="store_true", help="Wipe and rebuild.")
    parser.add_argument("--dry-run", action="store_true", help="Show docs without adding.")
    args = parser.parse_args()

    populate(reset=args.reset, dry_run=args.dry_run)


if __name__ == "__main__":
    main()