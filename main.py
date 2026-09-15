"""
main.py — Spectre Impact FastAPI backend.

Endpoints:
    GET  /ping                    — health check.
    GET  /health/memory           — memory backend status.
    POST /webhook                 — GitHub webhook receiver (PR + push).
    GET  /api/analyses            — list recent analyses.
    GET  /api/analyses/{pr}       — full analysis for a PR.
    GET  /api/metrics             — aggregate metrics.
    POST /api/chat                — Lya chat endpoint.
    POST /api/chat/clear          — clear a session's history.

Design notes:
    - The BFS logic now delegates to backend.analysis.change_analysis_engine
      .analyze_impact(), which is the single source of truth. The old inline
      BFS in this file was removed to avoid duplication and schema drift.
    - The chat endpoints use chat.agent + chat.memory. They degrade
      gracefully if those modules are missing.
"""

import sys
import os
import json
import yaml
import hashlib
import traceback
from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from github import Github, GithubException, Auth

# Force UTF-8 for Windows
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
# Spectre Impact internal imports
# -------------------------------------------------------------------
from database import (
    get_all_analyses,
    get_pr_analysis,
    save_analysis,
    is_commit_analyzed,
    save_commit_analysis,
)
from github_client import (
    post_github_comment,
    post_inline_comment,
    get_pr_for_branch,
    fetch_commit_diff,
)

# BFS engine — the single source of truth
try:
    from backend.analysis.change_analysis_engine import analyze_impact
    log("✅ analyze_impact imported")
except ImportError as e:
    log(f"⚠️ analyze_impact import failed: {e}")

    def analyze_impact(changed_files):
        return {
            "changed_resource": "unknown",
            "changed_resources": [],
            "affected_services": [],
            "business_impact": 0,
            "unknown_resources": changed_files,
            "evidence": [],
        }


# AI agent (Groq-based insights + code review)
try:
    from ai_agent_groq import (
        generate_insights,
        generate_inline_suggestions,
        generate_code_review,
    )
    log("✅ AI agent imported")
except ImportError as e:
    log(f"⚠️ AI agent import failed: {e}")

    def generate_insights(services, impact):
        return {
            "simulation": "AI unavailable – using fallback.",
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
    log("✅ Cache imported")
except ImportError as e:
    log(f"⚠️ Cache import failed: {e}")

    def get_cached_diff_suggestions(key): return None
    def cache_diff_suggestions(key, suggestions): pass
    def get_cache_key_for_diff(diff): return hashlib.md5(diff.encode()).hexdigest()


# Lya chat agent — memory, agent, safety (all optional)
try:
    from chat.agent import chat as lya_chat
    from chat.memory import (
        get_history,
        save_message,
        clear_session,
        health as memory_health,
    )
    log("✅ Lya chat agent imported")
except ImportError as e:
    log(f"⚠️ Lya chat import failed: {e}")

    async def lya_chat(message, history=None, tools=None):
        return {"response": "Chat agent unavailable.", "tool_calls": []}

    def get_history(sid, limit=None): return []
    def save_message(sid, role, content): pass
    def clear_session(sid): pass
    def memory_health(): return {"backend": "unavailable"}


try:
    from chat.safety import sanitize_input, sanitize_output
    log("✅ Safety module imported")
except ImportError:
    # Safety module not yet built — safe no-op fallbacks.
    def sanitize_input(text): return text
    def sanitize_output(text): return text


# -------------------------------------------------------------------
# Blast radius — delegates to the real engine
# -------------------------------------------------------------------
def calculate_blast_radius(changed_files: list[str]) -> dict[str, Any]:
    """
    Compute the blast radius of a set of changed files.

    Delegates to backend.analysis.change_analysis_engine.analyze_impact —
    the single source of truth used by the chat tools and the code review
    pipeline. This replaces the old inline BFS that duplicated the logic.
    """
    if not changed_files:
        return {
            "changed_resource": "unknown",
            "affected_services": ["unknown_service"],
            "business_impact": 0,
        }

    try:
        result = analyze_impact(changed_files)
    except Exception as exc:
        log(f"❌ analyze_impact failed: {exc}\n{traceback.format_exc()}")
        return {
            "changed_resource": "unknown",
            "affected_services": ["unknown_service"],
            "business_impact": 0,
        }

    affected = result.get("affected_services") or ["unknown_service"]
    return {
        "changed_resource": result.get("changed_resource", "unknown"),
        "affected_services": affected,
        "business_impact": result.get("business_impact", 0),
    }


# -------------------------------------------------------------------
# FastAPI app
# -------------------------------------------------------------------
app = FastAPI(title="Spectre Impact")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


# -------------------------------------------------------------------
# Pydantic models
# -------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(..., min_length=1, max_length=128)


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tool_calls: list[str] = []


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
# Lya chat
# -------------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest) -> ChatResponse:
    """
    Send a message to Lya and get a response.

    Flow:
        1. Sanitize input (blocks prompt injection).
        2. Load session history.
        3. Call the agent.
        4. Save user message + assistant reply.
        5. Sanitize output (strips secrets).
        6. Return the reply.
    """
    log(f"💬 /api/chat session={req.session_id} len={len(req.message)}")

    # 1. Sanitize input
    try:
        clean_message = sanitize_input(req.message)
    except ValueError as exc:
        log(f"🚫 Blocked input in {req.session_id}: {exc}")
        raise HTTPException(status_code=400, detail="Invalid input.") from exc

    # 2. Load history
    history = get_history(req.session_id)

    # 3. Call agent
    try:
        result = await lya_chat(clean_message, history=history)
    except Exception as exc:
        log(f"❌ Chat failed: {exc}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Chat failed.") from exc

    # 4. Save to memory
    save_message(req.session_id, "user", clean_message)
    save_message(req.session_id, "assistant", result.get("response", ""))

    # 5. Sanitize output
    safe_response = sanitize_output(result.get("response", ""))

    # 6. Return
    return ChatResponse(
        response=safe_response,
        session_id=req.session_id,
        tool_calls=result.get("tool_calls", []),
    )


@app.post("/api/chat/clear")
async def chat_clear(session_id: str) -> dict[str, Any]:
    """Clear a session's conversation history."""
    clear_session(session_id)
    log(f"🧹 Cleared session {session_id}")
    return {"status": "cleared", "session_id": session_id}


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
        log("⚠️ GITHUB_TOKEN missing – cannot fetch files.")
        return []
    try:
        auth = Auth.Token(GITHUB_TOKEN)
        g = Github(auth=auth)
        repo = g.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        return [f.filename for f in pr.get_files()]
    except GithubException as e:
        log(f"❌ GitHub API error: {e}")
        return []
    except Exception as e:
        log(f"❌ Unexpected error fetching files: {e}")
        return []


def get_commit_sha_from_pr(repo_name: str, pr_number: int) -> str | None:
    if not GITHUB_TOKEN:
        log("⚠️ GITHUB_TOKEN not set – cannot get commit SHA.")
        return None
    try:
        auth = Auth.Token(GITHUB_TOKEN)
        g = Github(auth=auth)
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        for commit in pr.get_commits():
            return commit.sha
        log(f"⚠️ No commits found in PR #{pr_number}")
        return None
    except GithubException as e:
        log(f"❌ GitHub API error getting commit SHA: {e}")
        return None
    except Exception as e:
        log(f"❌ Unexpected error getting commit SHA: {e}")
        return None


# -------------------------------------------------------------------
# PR analysis pipeline (unchanged logic, uses new calculate_blast_radius)
# -------------------------------------------------------------------
def run_analysis_pipeline(pr_number: int, repo_name: str, action: str) -> None:
    log(f"🚀 Pipeline started for PR #{pr_number} in {repo_name}")
    changed_files = fetch_changed_files(repo_name, pr_number)
    log(f"📄 Changed files: {changed_files}")

    try:
        blast = calculate_blast_radius(changed_files)
        log(f"💥 Blast radius: {blast}")
    except Exception as e:
        log(f"❌ BFS failed: {e}\n{traceback.format_exc()}")
        return

    commit_sha = get_commit_sha_from_pr(repo_name, pr_number)
    log(f"📝 Commit SHA: {commit_sha}")

    diff = ""
    if commit_sha:
        diff = fetch_commit_diff(repo_name, commit_sha)
    log(f"📝 Diff fetched: {len(diff)} characters")

    try:
        code_review = generate_code_review(diff, changed_files, blast.get("affected_services", []))
        log(f"🔍 Code review verdict: {code_review.get('overall_verdict', 'Unknown')}")
    except Exception as e:
        log(f"❌ Code review failed: {e}\n{traceback.format_exc()}")
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
        log(f"🤖 Insights generated: {insights.get('severity', 'Unknown')}")
    except Exception as e:
        log(f"❌ AI agent failed: {e}\n{traceback.format_exc()}")
        insights = {
            "simulation": "AI unavailable – using fallback.",
            "severity": "Medium",
            "rollback": ["Revert changes", "Restart services"],
            "validation": ["Check health endpoints"],
            "tokens_used": {},
        }

    try:
        save_analysis(pr_number, repo_name, blast, insights)
        log(f"💾 Saved analysis for PR #{pr_number}")
    except Exception as e:
        log(f"❌ Database save failed: {e}\n{traceback.format_exc()}")

    try:
        post_github_comment(pr_number, repo_name, blast, insights, code_review)
        log(f"📝 Comment posted to PR #{pr_number}")
    except Exception as e:
        log(f"❌ GitHub comment failed: {e}\n{traceback.format_exc()}")


# -------------------------------------------------------------------
# Commit analysis pipeline (unchanged)
# -------------------------------------------------------------------
def run_commit_analysis(repo_name: str, commit_sha: str, branch: str, changed_files: list) -> None:
    log(f"🚀 Auto-analyzing commit {commit_sha[:7]} on {branch}")

    try:
        blast = calculate_blast_radius(changed_files)
        log(f"💥 Blast radius: {blast}")
    except Exception as e:
        log(f"❌ BFS failed: {e}\n{traceback.format_exc()}")
        return

    diff = fetch_commit_diff(repo_name, commit_sha)
    if not diff:
        log("⚠️ No diff available – skipping inline analysis")
        return

    try:
        code_review = generate_code_review(diff, changed_files, blast.get("affected_services", []))
        log(f"🔍 Code review: {code_review.get('overall_verdict', 'Unknown')}")
    except Exception as e:
        log(f"❌ Code review failed: {e}\n{traceback.format_exc()}")
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
        log(f"📦 Using cached suggestions ({len(cached_suggestions)} items)")
        suggestions = cached_suggestions
    else:
        try:
            suggestions = generate_inline_suggestions(diff, changed_files, blast["affected_services"])
            log(f"💡 Generated {len(suggestions)} inline suggestions")
            if suggestions:
                cache_diff_suggestions(diff_key, suggestions)
        except Exception as e:
            log(f"❌ AI generation failed: {e}\n{traceback.format_exc()}")
            suggestions = []

    if suggestions:
        for s in suggestions:
            try:
                post_inline_comment(
                    repo_name,
                    commit_sha,
                    s.get("file"),
                    s.get("line"),
                    s.get("suggestion"),
                    s.get("severity", "High"),
                )
                log(f"📝 Posted inline comment on {s.get('file')}:{s.get('line')}")
            except Exception as e:
                log(f"❌ Failed to post inline comment: {e}")
    else:
        log("💡 No inline suggestions generated")

    try:
        pr_number = get_pr_for_branch(repo_name, branch)
        if pr_number:
            log(f"🔍 Found PR #{pr_number} for this branch")
            insights = generate_insights(blast["affected_services"], blast["business_impact"])
            post_github_comment(pr_number, repo_name, blast, insights, code_review)
            log(f"📝 Posted PR comment on #{pr_number}")
        else:
            log("ℹ️ No open PR found for this branch")
    except Exception as e:
        log(f"⚠️ PR comment failed: {e}")

    try:
        save_commit_analysis(
            commit_sha,
            repo_name,
            branch,
            changed_files,
            blast["affected_services"],
            blast["business_impact"],
            suggestions,
        )
        log(f"💾 Saved analysis for commit {commit_sha[:7]}")
    except Exception as e:
        log(f"❌ Database save failed: {e}\n{traceback.format_exc()}")

    log(f"✅ Commit analysis complete for {commit_sha[:7]}")


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

    log(f"🔥 Webhook received: PR #{pr_number}, {repo_name}, action={action}")
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
    log("🚀 Starting Spectre Impact server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)