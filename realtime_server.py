"""FastAPI webhook receiver for real GitHub events.

Run:
    uvicorn realtime_server:app --host 0.0.0.0 --port 8000

Configure GitHub webhook URL:
    https://<your-public-host>/webhook/github

The dashboard reads the same runtime_data/events.json store and refreshes
periodically, so a new webhook event becomes visible without restarting it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import hashlib
import hmac
import os

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
except Exception:  # pragma: no cover
    FastAPI = None

from ai_fallback import analyze_change
from bfs import calculate_blast_radius
from realtime import add_live_event, get_live_events, get_team_messages

if FastAPI is not None:
    app = FastAPI(title="Spectre Impact Realtime API", version="1.0")
else:
    app = None


def _normalize_files(payload: dict[str, Any]) -> list[str]:
    files = payload.get("changed_files")
    if isinstance(files, list):
        return [str(x) for x in files if x]

    pr = payload.get("pull_request") or {}
    files = pr.get("changed_files_list") or []
    if isinstance(files, list):
        return [str(x) for x in files if x]
    return []


def build_event(payload: dict[str, Any]) -> dict[str, Any]:
    pr = payload.get("pull_request") or {}
    repo = payload.get("repository") or {}
    sender = payload.get("sender") or {}
    commits = payload.get("commits") or []

    is_push = bool(commits) and not pr
    files = _normalize_files(payload)
    if is_push and not files:
        for commit in commits[:10]:
            for file_name in (commit.get("added") or []) + (commit.get("modified") or []) + (commit.get("removed") or []):
                if file_name not in files:
                    files.append(file_name)

    severity_hint = payload.get("severity", "UNKNOWN")
    analysis = analyze_change(files, severity_hint)
    severity = str(severity_hint or "UNKNOWN").upper()
    if severity not in {"HIGH", "MEDIUM", "LOW"}:
        severity = "HIGH" if len(files) >= 3 else "MEDIUM" if files else "LOW"

    author = (
        sender.get("login")
        or pr.get("user", {}).get("login")
        or (commits[0].get("author", {}).get("username") if commits else None)
        or "Unknown Developer"
    )
    if is_push:
        pr_number = f"commit:{payload.get('after', 'unknown')[:8]}"
        action = "push"
        message = (commits[0].get("message") if commits else None) or "Code push"
    else:
        pr_number = f"#{pr.get('number', payload.get('pr_number', 'UNKNOWN'))}"
        action = payload.get("action", "updated")
        message = pr.get("title") or payload.get("commit_message") or "Pull Request change"

    return {
        "event_id": str(payload.get("delivery") or f"github-{datetime.now(timezone.utc).timestamp()}"),
        "event_type": "push" if is_push else "pull_request",
        "action": action,
        "author": author,
        "repository": repo.get("full_name") or repo.get("name") or "Unknown Repository",
        "pr_number": pr_number,
        "commit_message": message,
        "changed_files": files,
        "severity": severity,
        "problem": analysis["problem"],
        "ai_analysis": analysis["summary"],
        "affected_services": analysis["affected_services"],
        "status": "needs_attention" if severity == "HIGH" else "review",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "github_webhook",
    }


if app is not None:
    @app.get("/health")
    def health():
        return {"status": "ok", "service": "spectre-realtime"}

    @app.get("/events")
    def events():
        return get_live_events(50)

    @app.get("/messages")
    def messages():
        return get_team_messages(100)

    @app.get("/prs")
    def prs():
        try:
            from data import DEFAULT_PRS, _merge_live_events
            return _merge_live_events(DEFAULT_PRS)
        except Exception:
            return []

    @app.post("/github/comment")
    async def github_comment(request: Request):
        """Optional real GitHub comment bridge. Requires GITHUB_TOKEN and repository."""
        import os
        import requests as http_requests
        try:
            body = await request.json()
            token = os.getenv("GITHUB_TOKEN", "").strip()
            repo = str(body.get("repository", "")).strip()
            pr_number = str(body.get("pr_number", "")).lstrip("#")
            comment = str(body.get("body", "")).strip()
            if not token or not repo or not pr_number or not comment:
                return JSONResponse({"ok": False, "error": "GitHub token, repository, PR number and comment are required."}, status_code=400)
            url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
            response = http_requests.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                json={"body": comment},
                timeout=6,
            )
            if not response.ok:
                return JSONResponse({"ok": False, "error": f"GitHub returned HTTP {response.status_code}."}, status_code=response.status_code)
            return {"ok": True, "url": response.json().get("html_url")}
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    @app.post("/webhook/github")
    async def github_webhook(request: Request):
        try:
            raw_body = await request.body()
            secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()
            signature = request.headers.get("x-hub-signature-256", "")
            if secret:
                expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
                if not hmac.compare_digest(expected, signature):
                    return JSONResponse({"ok": False, "error": "Invalid webhook signature."}, status_code=401)

            payload = await request.json()
            event = build_event(payload if isinstance(payload, dict) else {})
            saved = add_live_event(event)
            return JSONResponse({"ok": True, "event": saved})
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
