from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(".spectre")
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def save_config(config: dict[str, Any]) -> None:
    import yaml
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def resolve_token() -> str | None:
    return os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or load_config().get("github", {}).get("token")


def write_json(path: str | Path, payload: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return target
