"""Spectre Impact CLI.

Reuses the exact pipeline functions main.py's /webhook handler calls —
main.fetch_changed_files, backend.analysis.change_analysis_engine.analyze_impact,
ai_agent_groq.generate_insights — no new analysis logic here.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as installed_version

import typer
from rich.console import Console
from rich.table import Table

from ai_agent_groq import generate_insights
from backend.analysis.change_analysis_engine import analyze_impact
from main import fetch_changed_files

app = typer.Typer(help="Spectre Impact CLI")
console = Console()


@app.command()
def analyze(
    pr_number: int = typer.Argument(..., help="Pull request number"),
    repo: str = typer.Option(..., "--repo", help="Repository as owner/name"),
):
    """Run the blast-radius + AI analysis for a PR, same pipeline as /webhook."""
    changed_files = fetch_changed_files(repo, pr_number)
    if not changed_files:
        console.print(
            f"[yellow]No changed files found for {repo}#{pr_number} "
            "(check GITHUB_TOKEN, repo name, and PR number).[/yellow]"
        )
        raise typer.Exit(code=1)

    blast = analyze_impact(changed_files)
    insights = generate_insights(blast["affected_services"], blast["business_impact"])

    table = Table(title=f"Spectre Impact — {repo}#{pr_number}")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Affected services", ", ".join(blast["affected_services"]) or "none")
    table.add_row("Business impact", f"{blast['business_impact']}%")
    table.add_row("Severity", insights.get("severity", "Unknown"))
    rollback = insights.get("rollback", [])
    table.add_row("Rollback plan", "\n".join(rollback) if rollback else "none")

    console.print(table)


@app.command()
def version():
    """Print the installed version."""
    try:
        console.print(installed_version("spectre-impact"))
    except PackageNotFoundError:
        console.print("[red]spectre-impact is not installed[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
