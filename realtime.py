"""Real-time event + team communication data layer.

The dashboard reads events from a local JSON store by default. A FastAPI
webhook server (realtime_server.py) writes GitHub events into the same store.
If SPECTRE_DATA_API_URL is configured, the dashboard can also read remote
PR/event data and automatically falls back to the local store when the API is
unavailable.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import requests
except Exception:  # pragma: no cover - optional at runtime
    requests = None

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "runtime_data"
EVENTS_FILE = DATA_DIR / "events.json"
MESSAGES_FILE = DATA_DIR / "messages.json"

DEFAULT_EVENTS = [
    {
        "event_id": "demo-445",
        "event_type": "pull_request",
        "action": "synchronize",
        "author": "Yassin",
        "repository": "Spectre",
        "pr_number": "#445",
        "commit_message": "Update login connection handling",
        "changed_files": ["login.py", "database.tf", "docker-compose.yml"],
        "severity": "HIGH",
        "problem": "Login and checkout may lose database connectivity after deployment.",
        "ai_analysis": "The dependency chain suggests authentication and checkout risk. Validate database connectivity before release.",
        "affected_services": ["Login Service", "Payment Gateway", "Main Database"],
        "status": "needs_attention",
        "timestamp": "2026-08-15T20:00:00+00:00",
        "source": "demo",
    },
    {
        "event_id": "demo-443",
        "event_type": "pull_request",
        "action": "opened",
        "author": "Malak",
        "repository": "Spectre",
        "pr_number": "#443",
        "commit_message": "Refactor authentication middleware",
        "changed_files": ["auth_middleware.py", "session_manager.py"],
        "severity": "HIGH",
        "problem": "Authentication sessions may fail validation.",
        "ai_analysis": "The change touches the authentication path and may increase 401 responses.",
        "affected_services": ["Authentication", "API Gateway"],
        "status": "needs_attention",
        "timestamp": "2026-08-15T19:55:00+00:00",
        "source": "demo",
    },
]

DEFAULT_MESSAGES = [
    {
        "message_id": "demo-msg-1",
        "author": "Ahmed",
        "text": "I will check the API Gateway dependency for the latest authentication change.",
        "timestamp": "2026-08-15T20:01:00+00:00",
        "event_id": "demo-445",
    },
    {
        "message_id": "demo-msg-2",
        "author": "Yassin",
        "text": "I am preparing the rollback for the database connection change.",
        "timestamp": "2026-08-15T20:02:00+00:00",
        "event_id": "demo-445",
    },
]


def _ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not EVENTS_FILE.exists():
        _atomic_write(EVENTS_FILE, DEFAULT_EVENTS)
    if not MESSAGES_FILE.exists():
        _atomic_write(MESSAGES_FILE, DEFAULT_MESSAGES)


def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="spectre_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _read_json(path: Path, default: Any) -> Any:
    try:
        _ensure_store()
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value
    except Exception:
        return default


def _remote_get(path: str, default: Any) -> Any:
    """Optional remote data source. Never lets an API failure break the UI."""
    base = os.getenv("SPECTRE_DATA_API_URL", "").strip().rstrip("/")
    if not base or requests is None:
        return default
    try:
        response = requests.get(f"{base}/{path.lstrip('/')}", timeout=2.5)
        response.raise_for_status()
        return response.json()
    except Exception:
        return default


def get_live_events(limit: int = 10) -> list[dict[str, Any]]:
    remote = _remote_get("events", None)
    events = remote if isinstance(remote, list) else _read_json(EVENTS_FILE, DEFAULT_EVENTS)
    if not isinstance(events, list):
        return []
    return sorted(events, key=lambda item: str(item.get("timestamp", "")), reverse=True)[:limit]


def add_live_event(event: dict[str, Any]) -> dict[str, Any]:
    """Append an event safely. Used by the webhook server and demo controls."""
    _ensure_store()
    events = _read_json(EVENTS_FILE, [])
    if not isinstance(events, list):
        events = []
    event = dict(event or {})
    event.setdefault("event_id", f"event-{datetime.now(timezone.utc).timestamp()}")
    event.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    events.append(event)
    _atomic_write(EVENTS_FILE, events[-500:])
    return event


def get_team_messages(limit: int = 30) -> list[dict[str, Any]]:
    remote = _remote_get("messages", None)
    messages = remote if isinstance(remote, list) else _read_json(MESSAGES_FILE, DEFAULT_MESSAGES)
    if not isinstance(messages, list):
        return []
    return sorted(messages, key=lambda item: str(item.get("timestamp", "")))[:limit]


def add_team_message(author: str, text: str, event_id: str | None = None) -> bool:
    text = str(text or "").strip()
    author = str(author or "Developer").strip() or "Developer"
    if not text:
        return False
    messages = _read_json(MESSAGES_FILE, [])
    if not isinstance(messages, list):
        messages = []
    messages.append({
        "message_id": f"msg-{datetime.now(timezone.utc).timestamp()}",
        "author": author,
        "text": text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_id": event_id,
    })
    _atomic_write(MESSAGES_FILE, messages[-500:])
    return True


def get_realtime_status() -> dict[str, Any]:
    """Return a safe status object even if the optional remote API is down."""
    _ensure_store()
    api_url = os.getenv("SPECTRE_DATA_API_URL", "").strip()
    if not api_url:
        return {"status": "LIVE", "label": "LIVE", "detail": "Local event stream"}
    if requests is None:
        return {"status": "CACHED", "label": "CACHED", "detail": "Remote client unavailable; using local events"}
    try:
        response = requests.get(f"{api_url.rstrip('/')}/health", timeout=2)
        response.raise_for_status()
        return {"status": "LIVE", "label": "LIVE", "detail": "Webhook/API connected"}
    except Exception:
        return {"status": "CACHED", "label": "CACHED", "detail": "API unavailable; dashboard is using last known local data"}


def post_github_comment(pr_number: str, repository: str, body: str) -> tuple[bool, str]:
    """Post through the configured backend endpoint. Safe fallback when not configured."""
    base = os.getenv("SPECTRE_GITHUB_API_URL", "").strip().rstrip("/")
    if not base or requests is None:
        return False, "GitHub API endpoint is not configured yet."
    try:
        response = requests.post(
            base,
            json={"pr_number": pr_number, "repository": repository, "body": body},
            timeout=4,
        )
        if response.ok:
            return True, "GitHub comment posted successfully."
        return False, f"GitHub API returned HTTP {response.status_code}."
    except Exception:
        return False, "GitHub API is unavailable. The dashboard will keep working."
