"""
agent.py — The Lya chat agent (direct Groq, no LangChain).

Rate limits:
    Groq's free tier caps at 8000 tokens per minute. If we still hit a 429
    after retries, we fall back to `ai.multi_provider.call_ai()`, which
    routes through Google Gemini (free tier). The user never sees a
    rate-limit error on stage.

Public API:
    chat(message, session_id, user_id, history, tools) -> dict
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

from langchain_core.tools import BaseTool

from chat.prompts import SYSTEM_PROMPT
from chat.tools import ALL_TOOLS
from chat.memory import (
    get_history,
    get_session_context,
    record_incident,
    record_mood_signal,
    touch_session,
)

# Multi-provider fallback chain. Routes Groq -> Google -> deterministic.
from ai.multi_provider import call_ai


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
DEFAULT_MODEL = os.getenv("SPECTRE_CHAT_MODEL", "openai/gpt-oss-20b")
DEFAULT_TEMPERATURE = 0
MAX_TOKENS = 700
GROQ_TIMEOUT = 30.0

# Tool-calling loop. Every iteration is a separate Groq call. Cutting
# from 5 to 3 shaves ~2-4 seconds off a tool-heavy turn without losing
# the ability to chain tools (analyze -> list -> details is 3 hops).
MAX_TOOL_ITERATIONS = 3

# Retry policy for 429s. Keep the retries short: if two attempts fail,
# fall over to multi_provider rather than making the user wait longer.
GROQ_RETRY_ATTEMPTS = 2
GROQ_RETRY_BASE_WAIT = 4.0  # seconds

# History window. Each turn costs ~80-150 tokens. Six is enough to
# preserve thread while staying under the free-tier TPM limit.
HISTORY_TURN_LIMIT = 6

# Tool results going back into the model. ChromaDB results can be huge.
# 2000 chars is the sweet spot: substance without context bloat.
TOOL_RESULT_MAX_CHARS = 2000


# ---------------------------------------------------------------------------
# Orphan follow-up detection
# ---------------------------------------------------------------------------
_REFERENTIAL_PATTERNS = [
    r"\bthose\b", r"\bthem\b", r"\bthat\b", r"\bthese\b", r"\bthe same\b",
    r"\bwhich of\b", r"\bof those\b", r"\bpreviously\b", r"\bearlier\b",
    r"\babove\b", r"\bthe (?:one|list|above)\b",
    r"دول", r"ده", r"دي", r"اللي فات", r"اللي قلته", r"اللي قلتيه",
    r"إيه أخطرهم", r"أي واحدة فيهم",
]


def _looks_like_orphan_followup(
    message: str,
    history: list[dict[str, Any]] | None,
) -> bool:
    """Return True if the message is a short follow-up with no prior context."""
    if history:
        return False

    text = (message or "").strip()
    if not text:
        return False
    if len(text.split()) > 20:
        return False

    lowered = text.lower()
    for pattern in _REFERENTIAL_PATTERNS:
        if re.search(pattern, lowered):
            return True
    return False


_ORPHAN_REFUSAL = (
    "I don't have prior context in this session — which services or files "
    "are you asking about? Share the file path, PR number, or service name, "
    "and I'll analyze it for you."
)


# ---------------------------------------------------------------------------
# Mood signal detection
# ---------------------------------------------------------------------------
def _detect_mood_signals(message: str) -> list[str]:
    """Scan the user message for signals that suggest mood."""
    if not message:
        return []

    signals: list[str] = []
    stripped = message.strip()

    if re.search(r"\b[A-Z]{4,}\b", stripped):
        signals.append("all_caps")
    if stripped.count("!") >= 2:
        signals.append("exclamations")
    if len(stripped.split()) <= 3:
        signals.append("short_message")

    lower = stripped.lower()
    if any(p in lower for p in ("sorry", "my bad", "my fault")):
        signals.append("apology")

    vent_markers = (
        "i've been", "i have been", "ugh", "tired", "exhausted",
        "frustrated", "so done", "done with", "4 hours", "all day",
        "can't", "cant", "why does", "why is this",
    )
    if any(m in lower for m in vent_markers):
        signals.append("vent")

    return signals


# ---------------------------------------------------------------------------
# Service name extraction
# ---------------------------------------------------------------------------
_SERVICE_PATTERNS = [
    re.compile(r"\b([a-z][a-z0-9_]{2,}_service)\b"),
    re.compile(r"\b([a-z][a-z0-9_]{2,}_database)\b"),
    re.compile(r"\b([a-z][a-z0-9_]{2,}_cache)\b"),
    re.compile(r"\b([a-z][a-z0-9_]{2,}_api)\b"),
    re.compile(r"\b([a-z][a-z0-9_]{2,}_journey)\b"),
    re.compile(r"\b([a-z][a-z0-9_]{2,}_app)\b"),
]


def _extract_service_names(message: str) -> list[str]:
    if not message:
        return []
    found: set[str] = set()
    for pattern in _SERVICE_PATTERNS:
        for match in pattern.findall(message):
            found.add(match)
    return sorted(found)


# ---------------------------------------------------------------------------
# Session context formatting
# ---------------------------------------------------------------------------
def _format_context_block(ctx: dict[str, Any]) -> str:
    if not ctx:
        return ""

    lines: list[str] = []

    session_count = int(ctx.get("session_count", 0))
    turn_count = int(ctx.get("turn_count", 0))
    mood = ctx.get("mood", "unknown")

    if session_count > 1:
        lines.append(f"- This is session #{session_count} with this user.")
    if turn_count > 1:
        lines.append(f"- This is turn {turn_count} of the current session.")
    if mood and mood != "unknown":
        lines.append(f"- Current mood read: {mood}.")

    recent = ctx.get("recent_incidents") or []
    if recent:
        seen: list[str] = []
        for inc in reversed(recent):
            svc = inc.get("service")
            if svc and svc not in seen:
                seen.append(svc)
            if len(seen) >= 3:
                break
        if seen:
            lines.append(f"- Recently asked about: {', '.join(seen)}.")

    recurring = ctx.get("cross_session_topics") or []
    if recurring:
        lines.append(f"- Recurring topics: {', '.join(recurring[:3])}.")

    if not lines:
        return ""

    return "## Session context\n\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool schema conversion
# ---------------------------------------------------------------------------
def _schema_of(tool: BaseTool) -> dict[str, Any]:
    schema = getattr(tool, "args_schema", None)
    if schema is None:
        return {"type": "object", "properties": {}}

    if hasattr(schema, "model_json_schema"):
        try:
            return schema.model_json_schema()
        except Exception:
            pass
    if hasattr(schema, "schema"):
        try:
            return schema.schema()
        except Exception:
            pass
    if isinstance(schema, dict):
        return schema

    return {"type": "object", "properties": {}}


def _build_tool_schemas(tools: list[BaseTool]) -> list[dict[str, Any]]:
    schemas = []
    for tool in tools:
        schemas.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": (tool.description or "").strip(),
                "parameters": _schema_of(tool),
            },
        })
    return schemas


# ---------------------------------------------------------------------------
# Groq call with rate-limit retry
# ---------------------------------------------------------------------------
async def _groq_call_with_retry(
    client: Any,
    groq_sdk: Any,
    **kwargs: Any,
) -> Any:
    """Call Groq with a short retry on 429. Raises the last error if it persists."""
    last_exc: Exception | None = None

    for attempt in range(GROQ_RETRY_ATTEMPTS):
        try:
            return await asyncio.to_thread(
                client.chat.completions.create, **kwargs
            )
        except groq_sdk.RateLimitError as exc:
            last_exc = exc
            if attempt == GROQ_RETRY_ATTEMPTS - 1:
                logger.error("Groq 429 persisted through retries; falling over")
                break
            wait = GROQ_RETRY_BASE_WAIT * (attempt + 1)
            logger.warning(
                "Groq 429 (attempt %d/%d) — retrying in %.0fs",
                attempt + 1, GROQ_RETRY_ATTEMPTS, wait,
            )
            await asyncio.sleep(wait)

    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------
async def _execute_tool(tool: BaseTool, tool_input: dict[str, Any]) -> str:
    try:
        if hasattr(tool, "ainvoke"):
            result = await tool.ainvoke(tool_input)
        else:
            result = await asyncio.to_thread(tool.invoke, tool_input)
    except Exception as exc:
        logger.warning("Tool %s failed: %s", tool.name, exc)
        return f"Tool error: {exc}"

    if isinstance(result, str):
        text = result
    else:
        try:
            text = json.dumps(result, default=str, ensure_ascii=False)
        except Exception:
            text = str(result)

    if len(text) > TOOL_RESULT_MAX_CHARS:
        text = text[:TOOL_RESULT_MAX_CHARS] + "\n... [trimmed]"

    return text


# ---------------------------------------------------------------------------
# Fallback: when Groq is fully rate-limited, ask multi_provider instead.
# ---------------------------------------------------------------------------
def _call_multi_provider_fallback(
    groq_messages: list[dict[str, Any]],
) -> str:
    """
    Build a plain prompt from the Groq message list and route it through
    the multi-provider chain (Groq -> Google -> deterministic).
    """
    prompt_parts: list[str] = []
    for m in groq_messages:
        role = m.get("role", "user")
        content = m.get("content") or ""
        if not content:
            continue
        prompt_parts.append(f"{role.upper()}: {content}")
    prompt = "\n\n".join(prompt_parts)

    try:
        result = call_ai(prompt)
        text = (result or {}).get("text", "").strip()
        if text:
            return text
    except Exception as exc:  # noqa: BLE001
        logger.error("multi_provider fallback failed: %s", exc)

    return (
        "The assistant is briefly rate-limited. "
        "Try again in about 30 seconds."
    )


# ---------------------------------------------------------------------------
# Public chat function
# ---------------------------------------------------------------------------
async def chat(
    message: str,
    session_id: str,
    user_id: str = "anonymous",
    history: list[dict[str, Any]] | None = None,
    tools: list[BaseTool] | None = None,
) -> dict[str, Any]:
    """Send one message to Lya and return her response."""
    # 1. Touch the session
    try:
        touch_session(user_id, session_id)
    except Exception as exc:
        logger.warning("touch_session failed: %s", exc)

    # 2. Record mood signals
    try:
        for signal in _detect_mood_signals(message):
            record_mood_signal(user_id, signal)
    except Exception as exc:
        logger.warning("record_mood_signal failed: %s", exc)

    # 3. Record service mentions
    try:
        for service in _extract_service_names(message):
            record_incident(user_id, service)
    except Exception as exc:
        logger.warning("record_incident failed: %s", exc)

    # 4. Session context
    try:
        session_ctx = get_session_context(user_id)
    except Exception as exc:
        logger.warning("get_session_context failed: %s", exc)
        session_ctx = {}
    context_block = _format_context_block(session_ctx)

    # 5. History
    if history is None:
        try:
            history = get_history(session_id)
        except Exception as exc:
            logger.warning("get_history failed: %s", exc)
            history = []

    # 6. Orphan follow-up guard
    if _looks_like_orphan_followup(message, history):
        logger.info("Orphan follow-up detected — returning clarification")
        return {"response": _ORPHAN_REFUSAL, "tool_calls": []}

    # 7. Build messages
    if tools is None:
        tools = list(ALL_TOOLS)

    groq_messages: list[dict[str, Any]] = []

    system_content = SYSTEM_PROMPT
    if context_block:
        system_content = f"{SYSTEM_PROMPT}\n\n---\n\n{context_block}"
    groq_messages.append({"role": "system", "content": system_content})

    trimmed_history = (history or [])[-HISTORY_TURN_LIMIT:]
    for turn in trimmed_history:
        if not isinstance(turn, dict):
            continue
        role = (turn.get("role") or "user").lower()
        content = turn.get("content") or ""
        if not content:
            continue
        if role not in ("user", "assistant", "system"):
            role = "user"
        groq_messages.append({"role": role, "content": content})

    groq_messages.append({"role": "user", "content": message})

    # 8. Groq client
    try:
        import groq as groq_sdk
    except ImportError as exc:
        logger.error("groq SDK not available: %s", exc)
        fallback = _call_multi_provider_fallback(groq_messages)
        return {"response": fallback, "tool_calls": []}

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY missing")
        fallback = _call_multi_provider_fallback(groq_messages)
        return {"response": fallback, "tool_calls": []}

    client = groq_sdk.Groq(api_key=api_key, timeout=GROQ_TIMEOUT, max_retries=0)
    tool_schemas = _build_tool_schemas(tools)
    tools_used: list[str] = []

    # 9. Tool-calling loop
    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            response = await _groq_call_with_retry(
                client,
                groq_sdk,
                model=DEFAULT_MODEL,
                messages=groq_messages,
                tools=tool_schemas if tool_schemas else None,
                tool_choice="auto" if tool_schemas else None,
                temperature=DEFAULT_TEMPERATURE,
                max_tokens=MAX_TOKENS,
                reasoning_effort="low",
            )
        except Exception as exc:
            logger.exception("Groq call failed after retries — falling over to multi_provider")
            fallback = _call_multi_provider_fallback(groq_messages)
            return {
                "response": fallback,
                "tool_calls": tools_used,
                "error": str(exc),
            }

        choice = response.choices[0]
        msg = choice.message

        if not msg.tool_calls:
            content = msg.content or ""
            if not content:
                reasoning = getattr(msg, "reasoning", None) or ""
                content = reasoning
            return {"response": content, "tool_calls": tools_used}

        groq_messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            tools_used.append(tool_name)

            try:
                tool_input = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                tool_input = {}

            tool = next((t for t in tools if t.name == tool_name), None)
            if tool is None:
                result_str = f"Unknown tool: {tool_name}"
            else:
                result_str = await _execute_tool(tool, tool_input)

            groq_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

    logger.warning("Agent loop hit max iterations (%d)", MAX_TOOL_ITERATIONS)
    fallback = _call_multi_provider_fallback(groq_messages)
    return {"response": fallback, "tool_calls": tools_used}