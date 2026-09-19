from __future__ import annotations

import time

import typer
from rich.console import Console

from backend.analysis.change_analysis_engine import analyze_impact

console = Console()


def run(base: str = typer.Option("main"), interval: int = typer.Option(10, min=2, help="Seconds between checks")) -> None:
    console.print(f"Watching git changes against [cyan]{base}[/]. Press Ctrl+C to stop.")
    previous: tuple[str, ...] = ()
    try:
        while True:
            import subprocess
            proc = subprocess.run(["git", "diff", "--name-only", base], capture_output=True, text=True)
            files = tuple(sorted(f for f in proc.stdout.splitlines() if f.strip()))
            if files != previous:
                previous = files
                if files:
                    result = analyze_impact(list(files))
                    console.print(f"[cyan]Change detected:[/] {len(files)} files | impact={result['business_impact']}% | severity={result['severity']}")
                else:
                    console.print("[dim]Working tree is clean.[/]")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\nStopped.")
