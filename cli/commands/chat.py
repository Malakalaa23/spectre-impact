from __future__ import annotations

import typer
from rich.console import Console

from ai_agent_groq import generate_text
from rag.vector_store import query_documents

from chat.safety import sanitize_input, sanitize_output

console = Console()


def run(question: str = typer.Argument(..., help="Question about the project")) -> None:
    try:
        clean_question = sanitize_input(question)
    except ValueError as exc:
        console.print(f"[red]Input blocked by safety filter:[/] {exc}")
        raise typer.Exit(1)

    docs = query_documents(clean_question, 5)
    context = "\n\n".join(f"[{d['id']}] {d['text']}" for d in docs)
    prompt = f"Answer using the retrieved project context. If the context is insufficient, say so.\n\nCONTEXT:\n{context}\n\nQUESTION:\n{clean_question}"
    try:
        answer = generate_text(prompt)
        clean_answer = sanitize_output(answer.text)
        console.print(clean_answer)
        console.print(f"[dim]provider={answer.provider} model={answer.model}[/]")
    except Exception as exc:
        console.print(f"[red]AI unavailable:[/] {exc}")
        raise typer.Exit(1)

