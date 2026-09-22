"""
main.py — Spectre Impact FastAPI backend.

Endpoints:
    GET  /ping                    — health check.
    GET  /health/memory           — memory backend status.
    GET  /api/live-feed           — recent auto-fired demo events.
    GET  /api/landing/presets     — bilingual landing page content.
    GET  /chat                    — chat deep-link (opens the chat UI).
    POST /webhook                 — GitHub webhook receiver (PR + push).
    GET  /api/analyses            — list recent analyses.
    GET  /api/analyses/{pr}       — full analysis for a PR.
    GET  /api/metrics             — aggregate metrics.
    POST /api/chat                — Lya chat endpoint.
    POST /api/chat/clear          — clear a session's history.
    POST /api/tts                 — text-to-speech (MP3 output).
    POST /api/stt                 — speech-to-text (Whisper).
    POST /api/feedback            — record user feedback on an AI output.
    GET  /api/feedback/stats      — aggregate feedback counts (accuracy).

Design notes:
    - BFS delegates to backend.analysis.change_analysis_engine.analyze_impact().
    - Chat endpoints use chat.agent + chat.memory + chat.safety.
    - TTS uses ai.tts (Edge TTS, English + Egyptian Arabic).
    - STT uses ai.stt (faster-whisper, Egyptian Arabic + English).
    - A background task auto-fires synthetic PR events every 30 seconds.
    - user_id is preferred over session_id for cross-session memory; the
      server sets a signed cookie on first contact and reuses it after.
    - Every analyzed PR is added to the RAG knowledge base (learning loop),
      so future queries can cite it as a past incident.
    - calculate_blast_radius() returns the FULL BFS result, including the
      evidence path chain and the deterministic severity. Trimming it here
      would break github_client.py, which reads bfs_result["evidence"] to
      render the evidence chain in the PR comment.
    - Heavy models (STT + RAG embeddings) are pre-loaded at startup so the
      first user request is fast. Without this, the first /api/stt call
      exceeds the client timeout in Merna's Streamlit UI.
"""

import sys
import os
import json
import yaml
import uuid
import hashlib
import asyncio
import traceback
from datetime import datetime, timezone
from typing import Any
from collections import deque

from fastapi import BackgroundTasks, FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from github import Github, GithubException, Auth

# Force UTF-8 on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

load_dotenv()


# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
LOG_FILE = "webhook.log"


def log(msg: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except Exception:
        pass
    print(msg, flush=True)


# -------------------------------------------------------------------
# FastAPI app
# -------------------------------------------------------------------
app = FastAPI(title="Spectre Impact")

# Signed cookie session (for stable user_id across requests).
SESSION_SECRET = os.getenv("SESSION_SECRET", "spectre-impact-dev-secret-change-me")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=60 * 60 * 24 * 30,  # 30 days
)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


# -------------------------------------------------------------------
# Spectre Impact internal imports
# -------------------------------------------------------------------
from database import (
    get_all_analyses,
    get_pr_analysis,
    save_analysis,
    is_commit_analyzed,
    save_commit_analysis,
    save_feedback,
    get_feedback,
    get_feedback_stats,
)
from github_client import (
    post_github_comment,
    post_inline_comment,
    get_pr_for_branch,
    fetch_commit_diff,
)

# BFS engine
try:
    from backend.analysis.change_analysis_engine import analyze_impact
    log("analyze_impact imported")
except ImportError as e:
    log(f"analyze_impact import failed: {e}")

    def analyze_impact(changed_files):
        return {
            "changed_resource": "unknown",
            "changed_resources": [],
            "affected_services": [],
            "business_impact": 0,
            "unknown_resources": changed_files,
            "evidence": [],
        }


# AI agent
try:
    from ai_agent_groq import (
        generate_insights,
        generate_inline_suggestions,
        generate_code_review,
    )
    log("AI agent imported")
except ImportError as e:
    log(f"AI agent import failed: {e}")

    def generate_insights(services, impact):
        return {
            "simulation": "AI unavailable - using fallback.",
            "severity": "Medium",
            "rollback": ["Revert changes", "Restart services"],
            "validation": ["Check health endpoints"],
            "tokens_used": {},
        }

    def generate_inline_suggestions(diff, changed_files, affected_services):
        return []

    def generate_code_review(diff, changed_files, services):
        return {
            "code_quality": "Unable to Analyze",
            "bugs_found": [],
            "security_issues": [],
            "missing_tests": [],
            "suggestions": ["AI code review failed. Manual review recommended."],
            "overall_verdict": "Manual Review Required",
        }


# Cache
try:
    from cache import (
        get_cached_diff_suggestions,
        cache_diff_suggestions,
        get_cache_key_for_diff,
    )
    log("Cache imported")
except ImportError as e:
    log(f"Cache import failed: {e}")

    def get_cached_diff_suggestions(key): return None
    def cache_diff_suggestions(key, suggestions): pass
    def get_cache_key_for_diff(diff): return hashlib.md5(diff.encode()).hexdigest()


# Lya chat agent — new signature accepts user_id
try:
    from chat.agent import chat as lya_chat
    from chat.memory import (
        get_history,
        save_message,
        clear_session,
        health as memory_health,
    )
    log("Lya chat agent imported")
except ImportError as e:
    log(f"Lya chat import failed: {e}")

    async def lya_chat(message, session_id, user_id="anonymous", history=None, tools=None):
        return {"response": "Chat agent unavailable.", "tool_calls": []}

    def get_history(sid, limit=None): return []
    def save_message(sid, role, content): pass
    def clear_session(sid): pass
    def memory_health(): return {"backend": "unavailable"}


try:
    from chat.safety import sanitize_input, sanitize_output
    log("Safety module imported")
except ImportError:
    def sanitize_input(text): return text
    def sanitize_output(text): return text


# TTS — Edge TTS, English + Egyptian Arabic
try:
    from ai.tts import synthesize_async as tts_synthesize
    log("TTS module imported")
except ImportError as e:
    log(f"TTS module import failed: {e}")

    async def tts_synthesize(text, language="auto", voice=None):
        raise RuntimeError("TTS module not available")


# STT — faster-whisper, Egyptian Arabic + English
try:
    from ai.stt import transcribe_async as stt_transcribe
    log("STT module imported")
except ImportError as e:
    log(f"STT module import failed: {e}")

    async def stt_transcribe(audio_bytes, language=None):
        raise RuntimeError("STT module not available")


# -------------------------------------------------------------------
# Landing page presets (bilingual)
# -------------------------------------------------------------------
LANDING_PRESETS: dict[str, dict[str, Any]] = {
    "en": {
        "language": "en",
        "flag": "GB",
        "button_label": "English",
        "headline": "Spectre Impact",
        "subheadline": "Know what breaks before you deploy.",
        "tagline": "AI-powered GitHub change intelligence for DevOps teams",
        "welcome_message": (
            "Hi, I am Lya. I help you understand what a code change will break, "
            "who it affects, and how to roll it back. Ask me anything about your repo."
        ),
        "example_prompts": [
            "What services are affected by customer_database.tf?",
            "Show me past incidents affecting payment_service",
            "Who owns the checkout API?",
            "Would changing services/payment/app.py break production?",
            "What happened in PR #5?",
        ],
        "quick_actions": [
            {"label": "Analyze a file", "action": "analyze_file"},
            {"label": "Show incidents", "action": "show_incidents"},
            {"label": "List services", "action": "list_services"},
        ],
        "tts_default_voice": "en-us-female",
        "tts_language": "en",
    },
    "ar": {
        "language": "ar",
        "flag": "EG",
        "button_label": "مصري",
        "headline": "سبكتر إمباكت",
        "subheadline": "اعرف إيه اللي هيكسر قبل ما تعمل deploy.",
        "tagline": "منصة ذكاء اصطناعي لفهم تأثير تغييرات GitHub على فريق الـ DevOps",
        "welcome_message": (
            "أهلاً يا باشا، أنا ليا. هساعدك تعرف أي تغيير في الكود هيكسر إيه، "
            "وهيأثر على مين، وإزاي تعمل rollback بأمان. اسألني أي حاجة عن الريبو بتاعك."
        ),
        "example_prompts": [
            "إيه الخدمات اللي هتتأثر لو غيرت customer_database.tf؟",
            "وريني الحوادث اللي حصلت في payment_service",
            "مين صاحب الـ checkout API؟",
            "لو غيرت services/payment/app.py ممكن يحصل مشكلة؟",
            "إيه اللي حصل في PR #5؟",
        ],
        "quick_actions": [
            {"label": "حلّل ملف", "action": "analyze_file"},
            {"label": "وريني الحوادث", "action": "show_incidents"},
            {"label": "اعرض الخدمات", "action": "list_services"},
        ],
        "tts_default_voice": "ar-eg-female",
        "tts_language": "ar",
    },
}


# -------------------------------------------------------------------
# Blast radius
# -------------------------------------------------------------------
def calculate_blast_radius(changed_files: list[str]) -> dict[str, Any]:
    """
    Run the BFS engine and return the full analysis.

    The BFS engine returns far more than we use directly:
        - evidence: the BFS path to every affected node
        - severity / confidence / deployment_strategy / rollback_required
        - affected_* categorized lists (services, apis, frontends, etc.)

    All of that flows through to the PR comment formatter and the DB.
    Trimming it down here would lose information that downstream
    consumers need — specifically, github_client.py reads
    bfs_result["evidence"] to render the evidence chain in the PR
    comment, and bfs_result["severity"] is the deterministic severity
    that should override the AI's guess when available.

    Nothing downstream is required to use every field. Passing them
    through is free; dropping them is a bug.
    """
    if not changed_files:
        return {
            "changed_resource": "unknown",
            "affected_services": ["unknown_service"],
            "business_impact": 0,
            "evidence": [],
        }

    try:
        result = analyze_impact(changed_files)
    except Exception as exc:
        log(f"analyze_impact failed: {exc}\n{traceback.format_exc()}")
        return {
            "changed_resource": "unknown",
            "affected_services": ["unknown_service"],
            "business_impact": 0,
            "evidence": [],
        }

    # Ensure the fields downstream consumers expect are present. The BFS
    # engine should already provide these; the fallbacks are for when a
    # path through the engine doesn't set them.
    result.setdefault("changed_resource", "unknown")
    result.setdefault("affected_services", ["unknown_service"])
    result.setdefault("business_impact", 0)
    result.setdefault("evidence", [])

    return result


# -------------------------------------------------------------------
# Live Demo Ticket Stream
# -------------------------------------------------------------------
_LIVE_FEED: deque = deque(maxlen=50)
_live_feed_total_events: int = 0

_LIVE_FEED_SAMPLES = [
    ("terraform/customer_database.tf", "PR"),
    ("services/payment/app.py", "PR"),
    ("services/login/app.py", "PR"),
    ("apis/checkout.py", "Commit"),
    ("frontend/checkout.jsx", "PR"),
    ("terraform/redis.tf", "Commit"),
]

_live_feed_task: asyncio.Task | None = None
_live_feed_counter = 0


def _push_live_event(message: str, kind: str = "info", meta: dict | None = None) -> None:
    global _live_feed_total_events
    _live_feed_total_events += 1
    _LIVE_FEED.appendleft({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
        "kind": kind,
        "meta": meta or {},
    })


async def _run_live_demo_stream(interval_seconds: int = 30) -> None:
    global _live_feed_counter

    _push_live_event("Live demo stream started", kind="system")
    log("Live demo ticket stream started")

    while True:
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            log("Live demo ticket stream cancelled")
            return

        try:
            _live_feed_counter += 1
            file_path, kind = _LIVE_FEED_SAMPLES[_live_feed_counter % len(_LIVE_FEED_SAMPLES)]

            result = analyze_impact([file_path])
            affected = result.get("affected_services") or []
            impact = result.get("business_impact", 0)

            if kind == "PR":
                msg = (
                    f"PR #{100 + _live_feed_counter} analyzed - "
                    f"{file_path} -> {len(affected)} services, {impact}% impact"
                )
            else:
                msg = (
                    f"Commit {hashlib.md5(file_path.encode()).hexdigest()[:7]} analyzed - "
                    f"{file_path} -> {len(affected)} services affected"
                )

            _push_live_event(
                msg,
                kind="pr" if kind == "PR" else "commit",
                meta={"file": file_path, "affected": affected[:5], "impact": impact},
            )
            log(f"Live event: {msg}")

        except Exception as exc:
            log(f"Live feed task error: {exc}")
            _push_live_event(f"Analysis error: {str(exc)[:100]}", kind="error")


@app.on_event("startup")
async def _start_live_demo_stream() -> None:
    global _live_feed_task
    if _live_feed_task is None or _live_feed_task.done():
        _live_feed_task = asyncio.create_task(_run_live_demo_stream(interval_seconds=30))


@app.on_event("startup")
async def _preload_heavy_models() -> None:
    """
    Pre-load the STT model and the RAG embedding model at startup.

    Without this, the first user request to /api/stt or a RAG query
    pays the full model-load cost (30-90 seconds locally, minutes on
    a cold container), which exceeds the client-side timeout in
    Merna's Streamlit UI. Loading them once at boot moves the cost
    to container startup where judges never see it.

    Failures are logged and swallowed — a model that fails to load
    should not prevent the rest of the app from starting. The lazy
    loaders in ai.stt and rag.vector_store will retry on first use.
    """
    # Pre-load STT
    try:
        from ai.stt import _get_model as _stt_get_model
        await asyncio.to_thread(_stt_get_model)
        log("STT model pre-loaded")
    except Exception as exc:
        log(f"STT pre-load failed (will load on first use): {exc}")

    # Pre-load RAG embeddings
    try:
        from rag.vector_store import _get_model as _embed_get_model
        await asyncio.to_thread(_embed_get_model)
        log("Embedding model pre-loaded")
    except Exception as exc:
        log(f"Embedding pre-load failed (will load on first use): {exc}")


@app.on_event("shutdown")
async def _stop_live_demo_stream() -> None:
    global _live_feed_task
    if _live_feed_task is not None and not _live_feed_task.done():
        _live_feed_task.cancel()


# -------------------------------------------------------------------
# Pydantic models
# -------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(..., min_length=1, max_length=128)
    user_id: str | None = Field(None, max_length=128)


class ChatResponse(BaseModel):
    response: str
    session_id: str
    user_id: str
    tool_calls: list[str] = []


class FeedbackRequest(BaseModel):
    """
    User feedback on an AI-generated output.

    The verdict drives the learning loop: every "correct" is a positive
    signal, every "incorrect" a negative one. Notes are optional, capped
    at 1000 chars to keep the table small.

    target_type must be one of the four outputs we produce:
        analysis       — the blast radius + business impact summary
        insight        — the AI severity / simulation / rollback text
        code_review    — the code quality verdict
        chat_response  — a Lya reply
    """
    target_type: str = Field(..., pattern="^(analysis|insight|code_review|chat_response)$")
    target_id: str = Field(..., min_length=1, max_length=128)
    verdict: str = Field(..., pattern="^(correct|incorrect|partial)$")
    user_id: str | None = Field(None, max_length=128)
    notes: str | None = Field(None, max_length=1000)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    language: str = Field("auto", pattern="^(auto|ar|en)$")
    voice: str | None = None


# -------------------------------------------------------------------
# Health
# -------------------------------------------------------------------
@app.get("/ping")
def ping():
    return {"status": "alive"}


@app.get("/health/memory")
def health_memory():
    return memory_health()


# -------------------------------------------------------------------
# Landing page presets
# -------------------------------------------------------------------
@app.get("/api/landing/presets")
def landing_presets() -> dict[str, Any]:
    """Return bilingual landing page content for the frontend."""
    return {
        "available_languages": list(LANDING_PRESETS.keys()),
        "default": "en",
        "presets": LANDING_PRESETS,
    }


# -------------------------------------------------------------------
# Chat deep-link
# -------------------------------------------------------------------
@app.get("/chat")
def chat_deep_link(
    request: Request,
    q: str = "",
    pr: int | None = None,
    lang: str = "en",
) -> dict[str, Any]:
    """
    Deep-link endpoint for chat.

    When someone clicks "Ask Lya about this change" from a PR comment, they
    land here. The frontend pre-fills the chat input with `q` and uses the
    returned session_id + user_id to continue the conversation.

    Query params:
        q     — the pre-filled question (URL-encoded)
        pr    — optional PR number for context
        lang  — "en" or "ar" (default "en")

    Returns:
        session_id         — stable session for this browser tab
        user_id            — stable user ID across sessions
        prefilled_question — the q param, echoed back
        pr_number          — the pr param, echoed back
        language           — the lang param
        presets            — landing preset for that language
    """
    session_id = request.session.get("spectre_session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session["spectre_session_id"] = session_id

    user_id = request.session.get("spectre_user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
        request.session["spectre_user_id"] = user_id

    # If lang is unknown, fall back to English
    if lang not in LANDING_PRESETS:
        lang = "en"

    return {
        "session_id": session_id,
        "user_id": user_id,
        "prefilled_question": q,
        "pr_number": pr,
        "language": lang,
        "presets": LANDING_PRESETS[lang],
    }


# -------------------------------------------------------------------
# Live feed
# -------------------------------------------------------------------
@app.get("/api/live-feed")
def live_feed(limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(limit, 50))
    events = list(_LIVE_FEED)[:limit]
    return {
        "count": len(events),
        "total": _live_feed_total_events,
        "buffer_size": len(_LIVE_FEED),
        "events": events,
    }


# -------------------------------------------------------------------
# Lya chat
# -------------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request) -> ChatResponse:
    """
    Send a message to Lya and get a response.

    user_id resolution order:
        1. From the request body (explicit).
        2. From the signed cookie session.
        3. Generate a new one and store it in the session.

    The resolved user_id is returned in the response so the frontend can
    persist it if it wants to control identity across devices.
    """
    log(f"/api/chat session={req.session_id} user={req.user_id or '(cookie)'} len={len(req.message)}")

    # Resolve user_id
    user_id = req.user_id
    if not user_id:
        user_id = request.session.get("spectre_user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
    request.session["spectre_user_id"] = user_id

    # Sanitize input
    try:
        clean_message = sanitize_input(req.message)
    except ValueError as exc:
        log(f"Blocked input in {req.session_id}: {exc}")
        raise HTTPException(status_code=400, detail="Invalid input.") from exc

    # Load history for the session
    history = get_history(req.session_id)

    # Call the agent (new signature: message, session_id, user_id, history)
    try:
        result = await lya_chat(
            clean_message,
            req.session_id,
            user_id=user_id,
            history=history,
        )
    except Exception as exc:
        log(f"Chat failed: {exc}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Chat failed.") from exc

    # Persist
    save_message(req.session_id, "user", clean_message)
    save_message(req.session_id, "assistant", result.get("response", ""))

    safe_response = sanitize_output(result.get("response", ""))

    return ChatResponse(
        response=safe_response,
        session_id=req.session_id,
        user_id=user_id,
        tool_calls=result.get("tool_calls", []),
    )


@app.post("/api/chat/clear")
async def chat_clear(session_id: str) -> dict[str, Any]:
    """Clear a session's conversation history. Does not clear user memory."""
    clear_session(session_id)
    log(f"Cleared session {session_id}")
    return {"status": "cleared", "session_id": session_id}


# -------------------------------------------------------------------
# Feedback (AI learning loop)
# -------------------------------------------------------------------
@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest, request: Request) -> dict[str, Any]:
    """
    Record feedback on an AI-generated output.

    user_id resolution is the same as /api/chat: body, then cookie, then
    a fresh UUID stored on the session.

    Returns the new row's id plus the current aggregate stats, so the
    frontend can show "thanks, accuracy is now X%" without a second call.
    """
    # Resolve user_id
    user_id = req.user_id
    if not user_id:
        user_id = request.session.get("spectre_user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
    request.session["spectre_user_id"] = user_id

    # Cap the notes string at the Pydantic limit; strip trailing whitespace
    notes = (req.notes or "").strip() or None

    try:
        feedback_id = save_feedback(
            target_type=req.target_type,
            target_id=req.target_id,
            verdict=req.verdict,
            user_id=user_id,
            notes=notes,
        )
    except ValueError as exc:
        # Pydantic pattern should catch this first, but defense in depth
        log(f"Feedback rejected: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log(
        f"/api/feedback id={feedback_id} type={req.target_type} "
        f"target={req.target_id} verdict={req.verdict} user={user_id}"
    )

    return {
        "status": "recorded",
        "feedback_id": feedback_id,
        "user_id": user_id,
        "stats": get_feedback_stats(),
    }


@app.get("/api/feedback/stats")
def feedback_stats() -> dict[str, Any]:
    """Return aggregate feedback counts and current accuracy."""
    return get_feedback_stats()


@app.get("/api/feedback/recent")
def feedback_recent(limit: int = 20) -> dict[str, Any]:
    """
    Return the most recent feedback entries.

    Bounded to 100 to keep responses small. Used by the dashboard for
    the "the AI learned this" demo panel.
    """
    limit = max(1, min(limit, 100))
    return {"count": limit, "entries": get_feedback(limit)}


# -------------------------------------------------------------------
# Text-to-speech
# -------------------------------------------------------------------
@app.post("/api/tts")
async def tts_endpoint(req: TTSRequest):
    log(f"/api/tts lang={req.language} chars={len(req.text)}")

    try:
        audio_bytes = await tts_synthesize(
            req.text,
            language=req.language,
            voice=req.voice,
        )
    except Exception as exc:
        log(f"TTS failed: {exc}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"TTS failed: {exc}") from exc

    if not audio_bytes:
        raise HTTPException(status_code=500, detail="TTS produced empty audio")

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": 'inline; filename="lya.mp3"',
            "Cache-Control": "no-store",
        },
    )


# -------------------------------------------------------------------
# Speech-to-text
# -------------------------------------------------------------------
@app.post("/api/stt")
async def stt_endpoint(
    audio: UploadFile = File(...),
    session_id: str = Form(""),
):
    """
    Transcribe uploaded audio to text.

    The frontend (Streamlit's st.audio_input) sends a webm/mp3/wav blob
    as multipart form data under the field name "audio".

    Returns:
        {"text": "...", "session_id": "...", "language": "ar" | "en"}
    """
    log(f"/api/stt session={session_id or '(none)'}")

    try:
        audio_bytes = await audio.read()
    except Exception as exc:
        log(f"Failed to read uploaded audio: {exc}")
        raise HTTPException(status_code=400, detail="Could not read audio file") from exc

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # Cap at 10 MB. A minute of webm audio is roughly 500 KB, so this
    # is generous. Prevents memory blowups from runaway uploads.
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio too large (max 10 MB)")

    try:
        text = await stt_transcribe(audio_bytes, language=None)
    except RuntimeError as exc:
        log(f"STT unavailable: {exc}")
        raise HTTPException(status_code=503, detail="Speech-to-text is not available") from exc
    except Exception as exc:
        log(f"STT failed: {exc}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Transcription failed") from exc

    # Detect the language of the transcript for the frontend. Arabic
    # characters in the output mean the user spoke Arabic.
    has_arabic = any("\u0600" <= c <= "\u06ff" for c in text)
    language = "ar" if has_arabic else "en"

    log(f"/api/stt transcribed {len(audio_bytes)} bytes -> {len(text)} chars")

    return {
        "text": text,
        "session_id": session_id,
        "language": language,
    }


# -------------------------------------------------------------------
# GitHub helpers
# -------------------------------------------------------------------
def parse_payload(payload: dict):
    pr_number = payload.get("pull_request", {}).get("number")
    repo_full_name = payload.get("repository", {}).get("full_name")
    action = payload.get("action")
    return pr_number, repo_full_name, action


def fetch_changed_files(repo_full_name: str, pr_number: int) -> list:
    if not GITHUB_TOKEN:
        log("GITHUB_TOKEN missing - cannot fetch files.")
        return []
    try:
        auth = Auth.Token(GITHUB_TOKEN)
        g = Github(auth=auth)
        repo = g.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        return [f.filename for f in pr.get_files()]
    except GithubException as e:
        log(f"GitHub API error: {e}")
        return []
    except Exception as e:
        log(f"Unexpected error fetching files: {e}")
        return []


def get_commit_sha_from_pr(repo_name: str, pr_number: int) -> str | None:
    if not GITHUB_TOKEN:
        log("GITHUB_TOKEN not set - cannot get commit SHA.")
        return None
    try:
        auth = Auth.Token(GITHUB_TOKEN)
        g = Github(auth=auth)
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        for commit in pr.get_commits():
            return commit.sha
        log(f"No commits found in PR #{pr_number}")
        return None
    except GithubException as e:
        log(f"GitHub API error getting commit SHA: {e}")
        return None
    except Exception as e:
        log(f"Unexpected error getting commit SHA: {e}")
        return None


# -------------------------------------------------------------------
# PR analysis pipeline
# -------------------------------------------------------------------
def run_analysis_pipeline(pr_number: int, repo_name: str, action: str) -> None:
    log(f"Pipeline started for PR #{pr_number} in {repo_name}")
    changed_files = fetch_changed_files(repo_name, pr_number)
    log(f"Changed files: {changed_files}")

    try:
        blast = calculate_blast_radius(changed_files)
        log(f"Blast radius: {blast.get('changed_resource')} -> "
            f"{len(blast.get('affected_services', []))} services, "
            f"{len(blast.get('evidence', []))} evidence paths")
        _push_live_event(
            f"Real PR #{pr_number} analyzed - {len(blast.get('affected_services', []))} services affected",
            kind="pr",
        )
    except Exception as e:
        log(f"BFS failed: {e}\n{traceback.format_exc()}")
        return

    commit_sha = get_commit_sha_from_pr(repo_name, pr_number)
    log(f"Commit SHA: {commit_sha}")

    diff = ""
    if commit_sha:
        diff = fetch_commit_diff(repo_name, commit_sha)
    log(f"Diff fetched: {len(diff)} characters")

    try:
        code_review = generate_code_review(diff, changed_files, blast.get("affected_services", []))
        log(f"Code review verdict: {code_review.get('overall_verdict', 'Unknown')}")
    except Exception as e:
        log(f"Code review failed: {e}\n{traceback.format_exc()}")
        code_review = {
            "code_quality": "Unable to Analyze",
            "bugs_found": [],
            "security_issues": [],
            "missing_tests": [],
            "suggestions": ["AI code review failed. Manual review recommended."],
            "overall_verdict": "Manual Review Required",
        }

    try:
        insights = generate_insights(blast["affected_services"], blast["business_impact"])
        log(f"Insights generated: {insights.get('severity', 'Unknown')}")
    except Exception as e:
        log(f"AI agent failed: {e}\n{traceback.format_exc()}")
        insights = {
            "simulation": "AI unavailable - using fallback.",
            "severity": "Medium",
            "rollback": ["Revert changes", "Restart services"],
            "validation": ["Check health endpoints"],
            "tokens_used": {},
        }

    # Prefer the deterministic BFS severity over the AI's guess. The BFS
    # returns uppercase ("CRITICAL"); github_client.py expects the
    # capitalized form ("Critical"). Normalize, then overwrite the AI
    # severity only when BFS produced a valid value.
    bfs_severity = (blast.get("severity") or "").strip().capitalize()
    if bfs_severity in ("Critical", "High", "Medium", "Low"):
        if insights.get("severity") != bfs_severity:
            log(f"Overriding AI severity ({insights.get('severity')}) with BFS severity ({bfs_severity})")
        insights["severity"] = bfs_severity

    try:
        save_analysis(pr_number, repo_name, blast, insights)
        log(f"Saved analysis for PR #{pr_number}")
    except Exception as e:
        log(f"Database save failed: {e}\n{traceback.format_exc()}")

    try:
        post_github_comment(pr_number, repo_name, blast, insights, code_review)
        log(f"Comment posted to PR #{pr_number}")
    except Exception as e:
        log(f"GitHub comment failed: {e}\n{traceback.format_exc()}")

    # Learning loop: add this analysis to the RAG knowledge base so future
    # queries can cite it as a past incident. Runs after the GitHub comment
    # so that a comment failure doesn't block the knowledge base growth, and
    # vice versa. Any failure here is logged and swallowed — RAG growth must
    # never break the main pipeline.
    try:
        from rag.populate import add_single_document

        doc_id = f"inc_pr_{pr_number}_{int(datetime.now(timezone.utc).timestamp())}"
        text = (
            f"Past incident: PR #{pr_number} in {repo_name}\n"
            f"Severity: {insights.get('severity', 'Unknown')}\n"
            f"Changed resource: {blast.get('changed_resource', 'unknown')}\n"
            f"Business impact: {blast.get('business_impact', 0)}%\n"
            f"Affected services: {', '.join(blast.get('affected_services', [])[:15])}\n"
        )
        simulation = insights.get("simulation")
        if simulation:
            text += f"Summary: {simulation[:400]}"

        add_single_document(
            doc_id=doc_id,
            text=text,
            metadata={"pr_number": pr_number, "repo": repo_name},
            doc_type="incident",
        )
        log(f"Added PR #{pr_number} to RAG knowledge base")
    except Exception as e:
        log(f"RAG addition failed: {e}")


# -------------------------------------------------------------------
# Commit analysis pipeline
# -------------------------------------------------------------------
def run_commit_analysis(repo_name: str, commit_sha: str, branch: str, changed_files: list) -> None:
    log(f"Auto-analyzing commit {commit_sha[:7]} on {branch}")

    try:
        blast = calculate_blast_radius(changed_files)
        log(f"Blast radius: {blast.get('changed_resource')} -> "
            f"{len(blast.get('affected_services', []))} services affected")
        _push_live_event(
            f"Real commit {commit_sha[:7]} analyzed - {len(blast.get('affected_services', []))} services affected",
            kind="commit",
        )
    except Exception as e:
        log(f"BFS failed: {e}\n{traceback.format_exc()}")
        return

    diff = fetch_commit_diff(repo_name, commit_sha)
    if not diff:
        log("No diff available - skipping inline analysis")
        return

    try:
        code_review = generate_code_review(diff, changed_files, blast.get("affected_services", []))
        log(f"Code review: {code_review.get('overall_verdict', 'Unknown')}")
    except Exception as e:
        log(f"Code review failed: {e}\n{traceback.format_exc()}")
        code_review = {
            "code_quality": "Unable to Analyze",
            "bugs_found": [],
            "security_issues": [],
            "missing_tests": [],
            "suggestions": ["AI code review failed. Manual review recommended."],
            "overall_verdict": "Manual Review Required",
        }

    diff_key = get_cache_key_for_diff(diff)
    cached_suggestions = get_cached_diff_suggestions(diff_key)

    if cached_suggestions is not None:
        log(f"Using cached suggestions ({len(cached_suggestions)} items)")
        suggestions = cached_suggestions
    else:
        try:
            suggestions = generate_inline_suggestions(diff, changed_files, blast["affected_services"])
            log(f"Generated {len(suggestions)} inline suggestions")
            if suggestions:
                cache_diff_suggestions(diff_key, suggestions)
        except Exception as e:
            log(f"AI generation failed: {e}\n{traceback.format_exc()}")
            suggestions = []

    if suggestions:
        for s in suggestions:
            try:
                post_inline_comment(
                    repo_name, commit_sha,
                    s.get("file"), s.get("line"),
                    s.get("suggestion"), s.get("severity", "High"),
                )
                log(f"Posted inline comment on {s.get('file')}:{s.get('line')}")
            except Exception as e:
                log(f"Failed to post inline comment: {e}")
    else:
        log("No inline suggestions generated")

    try:
        pr_number = get_pr_for_branch(repo_name, branch)
        if pr_number:
            log(f"Found PR #{pr_number} for this branch")
            insights = generate_insights(blast["affected_services"], blast["business_impact"])

            # Same severity normalization as the PR pipeline.
            bfs_severity = (blast.get("severity") or "").strip().capitalize()
            if bfs_severity in ("Critical", "High", "Medium", "Low"):
                insights["severity"] = bfs_severity

            post_github_comment(pr_number, repo_name, blast, insights, code_review)
            log(f"Posted PR comment on #{pr_number}")
        else:
            log("No open PR found for this branch")
    except Exception as e:
        log(f"PR comment failed: {e}")

    try:
        save_commit_analysis(
            commit_sha, repo_name, branch, changed_files,
            blast["affected_services"], blast["business_impact"], suggestions,
        )
        log(f"Saved analysis for commit {commit_sha[:7]}")
    except Exception as e:
        log(f"Database save failed: {e}\n{traceback.format_exc()}")

    log(f"Commit analysis complete for {commit_sha[:7]}")


# -------------------------------------------------------------------
# Webhook endpoint
# -------------------------------------------------------------------
@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored"}

    if not isinstance(payload, dict):
        return {"status": "ignored"}

    event_type = request.headers.get("X-GitHub-Event")

    if event_type == "push":
        repo_name = payload["repository"]["full_name"]
        branch = payload["ref"].replace("refs/heads/", "")
        commit_sha = payload["after"]

        changed_files = []
        for commit in payload.get("commits", []):
            changed_files.extend(commit.get("added", []))
            changed_files.extend(commit.get("modified", []))
        changed_files = list(set(changed_files))

        if not changed_files:
            return {"status": "no files changed"}

        if is_commit_analyzed(commit_sha):
            return {"status": "already analyzed"}

        background_tasks.add_task(
            run_commit_analysis,
            repo_name, commit_sha, branch, changed_files,
        )
        return {"status": "analyzing", "commit": commit_sha}

    if "pull_request" not in payload:
        return {"status": "ignored"}

    pr_number, repo_name, action = parse_payload(payload)
    if pr_number is None or repo_name is None:
        return {"status": "ignored"}

    if action not in ["opened", "reopened"]:
        return {"status": "ignored"}

    log(f"Webhook received: PR #{pr_number}, {repo_name}, action={action}")
    background_tasks.add_task(run_analysis_pipeline, pr_number, repo_name, action)
    return {"received": True}


# -------------------------------------------------------------------
# Dashboard API endpoints
# -------------------------------------------------------------------
@app.get("/api/analyses")
def list_analyses(limit: int = 50):
    return get_all_analyses(limit)


@app.get("/api/analyses/{pr_number}")
def read_pr_analysis(pr_number: int):
    return get_pr_analysis(pr_number)


@app.get("/api/metrics")
def metrics():
    analyses = get_all_analyses(limit=1000)
    total_prs = len(analyses)
    high_risk_prs = sum(1 for a in analyses if a.get("severity") in ("Critical", "High"))
    return {"total_prs": total_prs, "high_risk_prs": high_risk_prs}


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    log("Starting Spectre Impact server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)