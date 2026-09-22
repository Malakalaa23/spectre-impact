from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

from cli.utils import load_config, save_config

console = Console()


def run(token: str | None = typer.Option(None, prompt=False, help="GitHub token; omitted prompts securely")) -> None:
    token = token or typer.prompt("GitHub token", hide_input=True)
    config = load_config()
    config.setdefault("github", {})["token"] = token
    save_config(config)
    try:
        os.chmod(Path(".spectre/config.yaml"), 0o600)
    except OSError:
        pass
    console.print("[green]✓ GitHub token saved to .spectre/config.yaml[/]")
