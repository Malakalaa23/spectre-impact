from pathlib import Path

from rich.console import Console

from cli.utils import CONFIG_DIR, CONFIG_FILE, save_config

console = Console()


def run() -> None:
    CONFIG_DIR.mkdir(exist_ok=True)
    if not CONFIG_FILE.exists():
        save_config({
            "ai": {"providers": ["groq", "openai", "anthropic"]},
            "analysis": {"severity_threshold": 70, "auto_rollback_plan": True},
            "voice": {"enabled": True},
            "rag": {"path": ".spectre/chroma"},
        })
    (CONFIG_DIR / ".gitignore").write_text("config.local.yaml\nvoice_cache/\nchroma/\n", encoding="utf-8")
    console.print(f"[green]✓ Spectre initialized[/] — {Path(CONFIG_FILE)}")
