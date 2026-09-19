"""FastAPI application for Spectre Impact.

The API is stateless per request: no PR analysis, voice jobs, or user session
state is stored in module globals. This makes concurrent users independent.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.analysis.change_analysis_engine import analyze_impact
from code_review.reviewer import full_review
from backend.session_manager import sessions
from ai_agent_groq import generate_text
from voice.tts import fallback_audio, text_to_speech

app = FastAPI(title="Spectre Impact", version="1.0.0")


class AnalysisRequest(BaseModel):
    changed_files: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    diff: str = ""
    repo_path: str = "."


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class VoiceRequest(BaseModel):
    text: str | None = None
    voice: str = "default"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze")
def analyze(request: AnalysisRequest) -> dict[str, Any]:
    if not request.changed_files:
        raise HTTPException(status_code=400, detail="changed_files cannot be empty")
    return analyze_impact(request.changed_files)


@app.post("/api/review")
def review(request: ReviewRequest) -> dict[str, Any]:
    return full_review(request.diff, request.repo_path)


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")
    session_id = request.session_id or sessions.create()
    history = sessions.get(session_id)
    try:
        response = generate_text(request.message, system="""You are Alex, Spectre Impact's senior backend mentor. Use the conversation context supplied by the API. Be concise and practical.""")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    sessions.append(session_id, "user", request.message)
    sessions.append(session_id, "assistant", response.text)
    return {"session_id": session_id, "provider": response.provider, "model": response.model, "message": response.text, "history_size": len(history) + 2, "session_backend": sessions.backend}


@app.post("/api/voice/{pr_number}")
def voice(pr_number: int, request: VoiceRequest):
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required for this stateless endpoint")
    try:
        path = text_to_speech(text, request.voice, fallback_level="unknown")
    except (RuntimeError, ValueError) as exc:
        try:
            path = fallback_audio("unknown")
        except RuntimeError:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return FileResponse(path, media_type="audio/mpeg", filename=f"spectre-pr-{pr_number}.mp3")


def _valid_signature(raw: bytes, signature: str | None) -> bool:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret:
        return True
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.removeprefix("sha256="), expected)


@app.post("/webhook/github")
async def github_webhook(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if not _valid_signature(raw, request.headers.get("x-hub-signature-256")):
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid JSON") from exc
    changed_files = payload.get("changed_files", [])
    if not isinstance(changed_files, list):
        raise HTTPException(status_code=400, detail="changed_files must be a list")
    return {
        "action": payload.get("action"),
        "pr_number": (payload.get("pull_request") or {}).get("number"),
        "analysis": analyze_impact([str(path) for path in changed_files]),
    }
