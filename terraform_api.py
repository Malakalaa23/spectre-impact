"""
terraform_api.py — FastAPI router for the Terraform parser.

Exposes three endpoints under /api/parse-terraform:

    POST  /api/parse-terraform          Parse a directory or .tf file by path.
    GET   /api/parse-terraform/sample   Parse the bundled demo_terraform/ dir.
    GET   /api/parse-terraform/sample/html
                                        Same data, rendered as a page.

Wire it into main.py with two lines:

    from terraform_api import router as terraform_router
    app.include_router(terraform_router)

The `add_to_rag=true` flag writes every parsed resource into the RAG
knowledge base as a document, so the chat agent can answer questions
about freshly parsed infrastructure.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from terraform_parser import (
    parse_terraform_directory,
    parse_terraform_file,
    to_documents,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/parse-terraform", tags=["terraform"])

# Resolve once at import so the endpoints work regardless of the current
# working directory uvicorn was started from.
PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLE_DIR = PROJECT_ROOT / "demo_terraform"


class ParseRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=1024)
    add_to_rag: bool = False


def _graph_to_response(graph: dict, source: str) -> dict:
    """
    Flatten the graph into a response shape a frontend can consume
    directly: nodes map + edges list + meta.
    """
    nodes = graph.get("nodes") or {}
    edges: list[dict] = []
    for name, node in nodes.items():
        for child in node.get("children") or []:
            edges.append({"from": name, "to": child, "type": "affects"})
    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {**graph.get("meta", {}), "source": source},
    }


def _add_graph_to_rag(graph: dict) -> int:
    """
    Add each parsed resource to the RAG store as a document.

    Returns the number of documents successfully added. Failures are
    logged and skipped — RAG is a bonus, not a blocker for the parse.
    """
    try:
        from rag.populate import add_single_document
    except Exception as exc:
        logger.warning("RAG module unavailable, skipping ingest: %s", exc)
        return 0

    added = 0
    for doc in to_documents(graph):
        try:
            add_single_document(
                doc_id=doc["id"],
                text=doc["text"],
                metadata=doc["metadata"],
                doc_type="terraform_parse",
            )
            added += 1
        except Exception as exc:
            logger.warning("RAG ingest failed for %s: %s", doc["id"], exc)
    return added


def _resolve_target(raw: str) -> Path:
    """
    Turn a user-supplied path into an absolute path.

    Relative paths resolve against the project root, not the process
    cwd, so the demo works whether uvicorn was started from the repo
    root or a subdirectory.
    """
    target = Path(raw).expanduser()
    if not target.is_absolute():
        target = (PROJECT_ROOT / target).resolve()
    return target


@router.post("")
async def parse_path(request: ParseRequest) -> dict:
    """
    Parse Terraform at a server-side path.

    Accepts either a directory (parsed recursively for *.tf) or a single
    .tf file (its parent directory is parsed so cross-file references
    still resolve).
    """
    target = _resolve_target(request.path)

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {target}")

    if target.is_file():
        if target.suffix != ".tf":
            raise HTTPException(status_code=400, detail="Target is not a .tf file")
        # Fail fast with a clear error if the single file has no resources.
        if not parse_terraform_file(target):
            raise HTTPException(
                status_code=422,
                detail=f"No resources found in {target.name}",
            )
        graph = parse_terraform_directory(target.parent)
    else:
        graph = parse_terraform_directory(target)

    if not graph.get("nodes"):
        raise HTTPException(
            status_code=422,
            detail="No Terraform resources found under the target path",
        )

    response = _graph_to_response(graph, source=str(target))
    if request.add_to_rag:
        response["rag_documents_added"] = _add_graph_to_rag(graph)
    return response


@router.get("/sample")
async def parse_sample(add_to_rag: bool = False) -> dict:
    """
    Parse the bundled demo_terraform/ directory.

    This is the endpoint the stage demo hits — a stable path that does
    not depend on anything outside the repo.
    """
    if not SAMPLE_DIR.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Sample directory missing: {SAMPLE_DIR}",
        )

    graph = parse_terraform_directory(SAMPLE_DIR)
    response = _graph_to_response(graph, source="demo_terraform")
    if add_to_rag:
        response["rag_documents_added"] = _add_graph_to_rag(graph)
    return response


@router.get("/sample/html", response_class=HTMLResponse)
async def parse_sample_html() -> str:
    """
    Render the parsed sample as a self-contained page.

    No CDN, no JavaScript framework. Works offline. Used on stage so
    judges see a real graph, not raw JSON in a browser tab.
    """
    if not SAMPLE_DIR.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Sample directory missing: {SAMPLE_DIR}",
        )
    graph = parse_terraform_directory(SAMPLE_DIR)
    response = _graph_to_response(graph, source="demo_terraform")
    return _render_html(response)


def _render_html(response: dict) -> str:
    """Build the HTML page from a parse response."""
    nodes = response["nodes"]
    meta = response["meta"]

    type_colors = {
        "database": "#7c3aed",
        "cache": "#0891b2",
        "service": "#059669",
        "api": "#ea580c",
        "frontend": "#dc2626",
        "network": "#6b7280",
        "storage": "#ca8a04",
        "unknown": "#4b5563",
    }

    # Sort so the demo reads top-down: network, storage, database,
    # cache, service, api, frontend.
    type_order = {
        "network": 0, "storage": 1, "database": 2, "cache": 3,
        "service": 4, "api": 5, "frontend": 6, "unknown": 7,
    }
    sorted_names = sorted(
        nodes.keys(),
        key=lambda n: (type_order.get(nodes[n].get("type", "unknown"), 99), n),
    )

    cards: list[str] = []
    for name in sorted_names:
        node = nodes[name]
        node_type = node.get("type", "unknown")
        color = type_colors.get(node_type, "#4b5563")
        children = node.get("children") or []

        if children:
            children_html = "".join(
                f'<span class="child">{c}</span>' for c in children
            )
        else:
            children_html = '<span class="leaf">no downstream dependents</span>'

        address = node.get("terraform_address", "")
        source_file = node.get("source_file", "")

        cards.append(f"""
        <div class="card">
          <div class="head">
            <span class="badge" style="background:{color}">{node_type}</span>
            <span class="name">{name}</span>
          </div>
          <div class="meta">{address} <span class="dim">·</span> {source_file}</div>
          <div class="children">
            <span class="label">affects</span> {children_html}
          </div>
        </div>""")

    files_parsed = meta.get("files_parsed", 0)
    resources_found = meta.get("resources_found", 0)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spectre Impact — Terraform Parse</title>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
    background: #0b1020; color: #e5e7eb;
    padding: 40px 32px; min-height: 100vh;
  }}
  h1 {{ margin: 0 0 10px; font-size: 22px; font-weight: 600;
        letter-spacing: -0.01em; }}
  .summary {{ color: #9ca3af; font-size: 14px; margin-bottom: 28px; }}
  .summary b {{ color: #f9fafb; font-weight: 600; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 14px;
  }}
  .card {{
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 16px 18px;
  }}
  .head {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
  .badge {{
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em;
    color: #fff; padding: 3px 9px; border-radius: 999px; font-weight: 600;
  }}
  .name {{
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 14px; color: #f3f4f6; font-weight: 600;
  }}
  .meta {{
    font-size: 12px; color: #6b7280; margin-bottom: 12px;
    font-family: "SF Mono", Menlo, Consolas, monospace;
  }}
  .dim {{ opacity: 0.5; margin: 0 4px; }}
  .children {{ font-size: 13px; line-height: 1.7; }}
  .label {{
    color: #6b7280; margin-right: 8px;
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em;
  }}
  .child {{
    display: inline-block; background: #1f2937; color: #d1d5db;
    padding: 2px 9px; border-radius: 4px; margin: 2px 4px 2px 0;
    font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12px;
  }}
  .leaf {{ color: #4b5563; font-style: italic; font-size: 12px; }}
</style>
</head>
<body>
  <h1>Terraform Parse — Spectre Impact</h1>
  <div class="summary">
    <b>{files_parsed}</b> files parsed ·
    <b>{resources_found}</b> resources found ·
    source <b>{meta.get("source", "unknown")}</b>
  </div>
  <div class="grid">
    {"".join(cards)}
  </div>
</body>
</html>"""