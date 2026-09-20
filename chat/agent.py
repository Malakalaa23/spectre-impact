"""
agent.py — The Lya chat agent (LangChain 1.x).

Builds a LangChain 1.x agent using `langchain.agents.create_agent`, which
returns a compiled LangGraph. The agent uses Lya's personality (from
`chat.prompts`) and the tools from `chat.tools`.

Session awareness:
    On every chat call, the agent touches the session via `chat.memory`,
    reads the resulting context (mood, session age, turn count, recent
    incidents, cross-session patterns), and injects a compact context
    block into the system prompt. This is what makes Lya feel like a
    friend who has been paying attention.

    The user's message is scanned for mood signals before touching the
    session so the mood snapshot reflects the current turn.

Runtime guard:
    Before invoking the LLM, `chat()` checks whether the user's message
    looks like an orphan follow-up — a short question that references
    prior context ("those", "that", "which of them") — while the session
    has no history. If so, it returns a clarification request without
    calling the LLM.

Public API:
    build_agent(tools=None)     — construct a fresh agent graph.
    chat(message, session_id)   — send one message, get one response back.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_groq import ChatGroq

from chat.prompts import SYSTEM_PROMPT
from chat.tools import ALL_TOOLS
from chat.memory import (
    get_history,
    get_session_context,
    record_incident,
    record_mood_signal,
    touch_session,
)
from config import get_env


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_TEMPERATURE = 0


# ---------------------------------------------------------------------------
# Orphan follow-up detection
# ---------------------------------------------------------------------------
_REFERENTIAL_PATTERNS = [
    r"\bthose\b",
    r"\bthem\b",
    r"\bthat\b",
    r"\bthese\b",
    r"\bthe same\b",
    r"\bwhich of\b",
    r"\bof those\b",
    r"\bpreviously\b",
    r"\bearlier\b",
    r"\babove\b",
    r"\bthe (?:one|list|above)\b",
    # Egyptian Arabic equivalents
    r"دول",
    r"ده",
    r"دي",
    r"اللي فات",
    r"اللي قلته",
    r"اللي قلتيه",
    r"إيه أخطرهم",
    r"أي واحدة فيهم",
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
    """
    Scan the user message for signals that suggest mood.

    Signals are coarse — we don't try to be clever, just notice obvious
    things. The memory module weights them and produces a mood snapshot.

    Returns a list of signal names. Empty if nothing notable.
    """
    if not message:
        return []

    signals: list[str] = []
    stripped = message.strip()

    # All-caps words (at least 4 chars, not just "OK")
    if re.search(r"\b[A-Z]{4,}\b", stripped):
        signals.append("all_caps")

    # Multiple exclamations
    if stripped.count("!") >= 2:
        signals.append("exclamations")

    # Very short messages (fatigue, exhaustion)
    if len(stripped.split()) <= 3:
        signals.append("short_message")

    # Apologies (frustration)
    lower = stripped.lower()
    if any(p in lower for p in ("sorry", "my bad", "my fault")):
        signals.append("apology")

    # Venting language
    vent_markers = (
        "i've been", "i have been", "ugh", "tired", "exhausted",
        "frustrated", "so done", "done with", "4 hours", "all day",
        "can't", "cant", "why does", "why is this",
    )
    if any(m in lower for m in vent_markers):
        signals.append("vent")

    return signals


# ---------------------------------------------------------------------------
# Service name extraction (for incident tracking)
# ---------------------------------------------------------------------------
# Matches common patterns like `payment_service`, `customer_database.tf`,
# `services/payment/app.py`. Extracts the resource-ish token.
_SERVICE_PATTERNS = [
    re.compile(r"\b([a-z][a-z0-9_]{2,}_service)\b"),
    re.compile(r"\b([a-z][a-z0-9_]{2,}_database)\b"),
    re.compile(r"\b([a-z][a-z0-9_]{2,}_cache)\b"),
    re.compile(r"\b([a-z][a-z0-9_]{2,}_api)\b"),
    re.compile(r"\b([a-z][a-z0-9_]{2,}_journey)\b"),
    re.compile(r"\b([a-z][a-z0-9_]{2,}_app)\b"),
]


def _extract_service_names(message: str) -> list[str]:
    """Return any service-like tokens found in the message. Deduped."""
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
    """
    Build a compact context block to inject into the system prompt.

    Only includes fields that are present and meaningful. Never fabricates.
    Returns an empty string if there's nothing worth adding.
    """
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
        # Show last 3 unique services
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
# Model + prompt building
# ---------------------------------------------------------------------------
def _build_llm() -> ChatGroq:
    """Create the Groq chat model client."""
    api_key = get_env("GROQ_API_KEY")
    return ChatGroq(
        api_key=api_key,
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
    )


def build_agent(tools: list[BaseTool] | None = None):
    """Construct a fresh agent graph with the given tools."""
    if tools is None:
        tools = list(ALL_TOOLS)

    llm = _build_llm()
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )
    return agent


# ---------------------------------------------------------------------------
# Message conversion
# ---------------------------------------------------------------------------
def _to_message(turn: dict[str, Any]):
    """Convert a stored history turn into a LangChain message object."""
    role = (turn.get("role") or "user").lower()
    content = turn.get("content") or ""

    if role == "assistant":
        return AIMessage(content=content)
    if role == "system":
        return SystemMessage(content=content)
    return HumanMessage(content=content)


def _build_messages(
    message: str,
    history: list[dict[str, Any]] | None,
    context_block: str,
):
    """Build the message list for one agent invocation."""
    messages = []

    if context_block:
        # Inject the session context as a system message right after the
        # main prompt. LangGraph keeps system messages in the message list.
        messages.append(SystemMessage(content=context_block))

    for turn in history or []:
        if isinstance(turn, dict) and turn.get("content"):
            messages.append(_to_message(turn))

    messages.append(HumanMessage(content=message))
    return messages


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
    """
    Send one message to Lya and return her response.

    Steps:
        1. Touch the session — updates timing, counts, and mood.
        2. Scan the message for mood signals and record them.
        3. Extract service names and record them as incidents.
        4. Read back the full session context.
        5. Orphan follow-up guard.
        6. Build messages (including context block) and invoke the agent.

    Args:
        message: The user's message text.
        session_id: Unique session identifier (per tab/window).
        user_id: Stable user identifier for cross-session memory.
                 Defaults to "anonymous" for backwards compatibility.
        history: Optional explicit history. If None, loads from memory.
        tools: Optional tools. If None, uses ALL_TOOLS.

    Returns:
        A dict with:
            - "response": Lya's text reply
            - "tool_calls": list of tool names invoked
    """
    # 1. Touch the session (bumps turn_count, may bump session_count)
    try:
        touch_session(user_id, session_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("touch_session failed: %s", exc)

    # 2. Detect and record mood signals
    try:
        for signal in _detect_mood_signals(message):
            record_mood_signal(user_id, signal)
    except Exception as exc:  # noqa: BLE001
        logger.warning("record_mood_signal failed: %s", exc)

    # 3. Record service mentions as incidents
    try:
        for service in _extract_service_names(message):
            record_incident(user_id, service)
    except Exception as exc:  # noqa: BLE001
        logger.warning("record_incident failed: %s", exc)

    # 4. Read back the session context
    try:
        session_ctx = get_session_context(user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_session_context failed: %s", exc)
        session_ctx = {}
    context_block = _format_context_block(session_ctx)

    # 5. If history not supplied, load from memory
    if history is None:
        try:
            history = get_history(session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_history failed: %s", exc)
            history = []

    # 6. Orphan follow-up guard — runs after history is known
    if _looks_like_orphan_followup(message, history):
        logger.info("Orphan follow-up detected — returning clarification")
        return {
            "response": _ORPHAN_REFUSAL,
            "tool_calls": [],
        }

    # 7. Build agent and invoke
    agent = build_agent(tools)
    messages = _build_messages(message, history, context_block)

    try:
        result = await agent.ainvoke({"messages": messages})
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent invocation failed")
        return {
            "response": "I ran into a problem handling that. Please try again.",
            "tool_calls": [],
            "error": str(exc),
        }

    return {
        "response": _extract_final_text(result),
        "tool_calls": _extract_tool_calls(result),
    }


# ---------------------------------------------------------------------------
# Result extraction
# ---------------------------------------------------------------------------
def _extract_final_text(result: dict[str, Any]) -> str:
    """Pull the final assistant text out of the LangGraph result."""
    messages = result.get("messages") or []
    if not messages:
        return ""

    last = messages[-1]
    content = getattr(last, "content", "")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)

    return str(content)


def _extract_tool_calls(result: dict[str, Any]) -> list[str]:
    """Collect the names of tools that were called during the agent run."""
    names: list[str] = []
    for msg in result.get("messages") or []:
        calls = getattr(msg, "tool_calls", None)
        if calls:
            for call in calls:
                if isinstance(call, dict):
                    if name := call.get("name"):
                        names.append(name)
                elif name := getattr(call, "name", None):
                    names.append(name)
    return names