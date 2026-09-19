from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from cli.commands import analyze, auth, chat, config, init, rag, report, review, watch

app = typer.Typer(name="spectre", help="Spectre Impact — AI DevOps analysis in your terminal", no_args_is_help=True)
console = Console()

app.command(name="init")(init.run)
app.command(name="analyze")(analyze.run)
app.command(name="chat")(chat.run)
app.command(name="watch")(watch.run)
app.command(name="config")(config.run)
app.command(name="auth")(auth.run)
app.command(name="report")(report.run)
app.command(name="review")(review.run)
rag_app = typer.Typer(help="Manage the Spectre RAG knowledge base")
rag_app.command(name="ingest")(rag.ingest)
rag_app.command(name="search")(rag.search)
app.add_typer(rag_app, name="rag")


@app.command()
def version() -> None:
    console.print(Panel("[bold green]Spectre Impact v1.0.0[/]"))


if __name__ == "__main__":
    app()
