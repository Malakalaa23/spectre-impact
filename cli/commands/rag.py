from __future__ import annotations

import typer
from rich.console import Console

from rag.enrich import enrich_repository
from rag.vector_store import get_store, query_documents

console = Console()


def ingest(repository: str = typer.Argument("."), target_docs: int = typer.Option(0, help="Optional deterministic demo target")) -> None:
    count = enrich_repository(repository, target_docs=target_docs)
    console.print(f"[green]✓ Indexed {count} records[/] ({'ChromaDB' if get_store().using_chroma else 'JSON fallback'})")


def search(query: str = typer.Argument(...), limit: int = typer.Option(5, min=1, max=20)) -> None:
    for item in query_documents(query, limit):
        console.print(f"[bold]{item['id']}[/] {item['text'][:500]}")
