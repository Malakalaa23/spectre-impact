from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from backend.analysis.change_analysis_engine import analyze_impact
from cli.utils import write_json

console = Console()


def run(files: list[str] = typer.Argument(...), output: str = typer.Option("spectre-report.json")) -> None:
    result = analyze_impact(files)
    write_json(output, result)
    console.print(f"[green]✓ Report written:[/] {Path(output)}")
