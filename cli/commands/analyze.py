from __future__ import annotations

import subprocess
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from ai_agent_groq import generate_insights
from backend.analysis.change_analysis_engine import analyze_impact

console = Console()


def run(base: str = typer.Option("main", help="Git base ref"), head: Optional[str] = typer.Option(None, help="Git head ref")) -> None:
    cmd = ["git", "diff", "--name-only", base] + ([head] if head else [])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise typer.BadParameter("git is not installed")
    if result.returncode != 0:
        console.print(
            f"[red]git diff failed:[/] {result.stderr.strip()}",
            markup=False,
        )
        raise typer.Exit(1)
    files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    if not files:
        console.print("[yellow]No changes detected[/]")
        return
    analysis = analyze_impact(files)
    console.print(f"[cyan]Changed:[/] {', '.join(analysis['changed_resources']) or 'unknown'}")
    console.print(f"[cyan]Blast radius:[/] {len(analysis['affected_nodes'])} nodes")
    console.print(f"[cyan]Business impact:[/] {analysis['business_impact']}%")
    console.print(f"[cyan]Severity:[/] {analysis['severity']}")
    console.print(f"[cyan]Deployment:[/] {analysis['deployment_strategy']}")
    if analysis["unknown_resources"]:
        console.print(f"[yellow]Unknown:[/] {', '.join(analysis['unknown_resources'])}")
    ai = generate_insights(analysis["affected_nodes"], analysis["business_impact"], context=analysis)
    console.print(Panel(
        f"[bold]Severity:[/] {ai['severity']}\n"
        f"[bold]Simulation:[/] {ai['simulation']}\n"
        f"[bold]Rollback:[/] {ai['rollback']}\n"
        f"[bold]Validation:[/] {ai['validation']}",
        title="AI Guidance",
    ))
