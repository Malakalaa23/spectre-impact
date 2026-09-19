from __future__ import annotations

import typer
from rich.console import Console

from ai_agent_groq import generate_text
from rag.vector_store import query_documents

console = Console()


def run(question: str = typer.Argument(..., help="Question about the project")) -> None:
    docs = query_documents(question, 5)
    context = "\n\n".join(f"[{d['id']}] {d['text']}" for d in docs)
    prompt = f"Answer using the retrieved project context. If the context is insufficient, say so.\n\nCONTEXT:\n{context}\n\nQUESTION:\n{question}"
    try:
        answer = generate_text(prompt)
        console.print(answer.text)
        console.print(f"[dim]provider={answer.provider} model={answer.model}[/]")
    except Exception as exc:
        console.print(f"[red]AI unavailable:[/] {exc}")
        raise typer.Exit(1)
