from __future__ import annotations

import json

import typer
from rich.console import Console

from cli.utils import load_config, save_config

console = Console()


def run(key: str | None = typer.Argument(None), value: str | None = typer.Argument(None)) -> None:
    config = load_config()
    if key is None:
        console.print_json(json.dumps(config))
        return
    if value is None:
        current = config
        for part in key.split("."):
            current = current.get(part, {}) if isinstance(current, dict) else None
        console.print(current if current is not None else "")
        return
    current = config
    parts = key.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value
    save_config(config)
    console.print(f"[green]✓[/] {key} updated")
