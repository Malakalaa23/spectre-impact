"""
agent.py — The Lya chat agent (direct Groq, no LangChain).

History:
    The original implementation used `langchain.agents.create_agent`, which
    builds a compiled LangGraph. That framework added 74 seconds of overhead
    to a turn that should take 1-2 seconds (measured: raw Groq = 1.4s,
    LangChain agent = 74.7s). The overhead is inherent to the framework —
    it re-serializes the tool catalog, runs the state machine, and validates
    Pydantic schemas on every step.

    This version calls Groq directly and hand-rolls the tool-calling loop.
    Same behavior, same public API, ~15x faster.

Session awareness:
    On every chat call, we touch the session via `chat.memory`, read the
    resulting context (mood, session age, turn count, recent incidents,
    cross-session patterns), and append a compact context block to the
    system prompt.

Runtime guard:
    Before calling Groq, `chat()` checks whether the user's message looks
    like an orphan follow-up with no history. If so, it returns a
    clarification request without calling the model.

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


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
#
# Chat runs TWICE per user message in the tool-calling loop (once to plan
# tool calls, once to write the response). Latency matters. gpt-oss-20b
# responds in ~1 second on Groq from Egypt; gpt-oss-120b takes 3-5x longer
# for the same task and adds nothing Lya needs.
#
# Override with SPECTRE_CHAT_MODEL if a specific model is needed.
DEFAULT_MODEL = os.getenv("SPECTRE_CHAT_MODEL", "openai/gpt-oss-20b")
DEFAULT_TEMPERATURE = 0
MAX_TOKENS = 700
GROQ_TIMEOUT = 30.0
MAX_TOOL_ITERATIONS = 5


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
# Service name extraction (for incident tracking)
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
    """Build a compact context block to append to the system prompt."""
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
    """
    Convert a LangChain tool's args_schema into an OpenAI/Groq function
    schema. Handles Pydantic v1, Pydantic v2, and raw dict schemas.
    """
    schema = getattr(tool, "args_schema", None)
    if schema is None:
        return {"type": "object", "properties": {}}

    if hasattr(schema, "model_json_schema"):       # Pydantic v2
        try:
            return schema.model_json_schema()
        except Exception:
            pass
    if hasattr(schema, "schema"):                  # Pydantic v1
        try:
            return schema.schema()
        except Exception:
            pass
    if isinstance(schema, dict):
        return schema

    return {"type": "object", "properties": {}}


def _build_tool_schemas(tools: list[BaseTool]) -> list[dict[str, Any]]:
    """Build the `tools` argument for the Groq chat completion call."""
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
# Tool execution
# ---------------------------------------------------------------------------
async def _execute_tool(tool: BaseTool, tool_input: dict[str, Any]) -> str:
    """
    Run a LangChain tool with the given input. Returns the output as a
    string, JSON-serialized if it's structured.
    """
    try:
        if hasattr(tool, "ainvoke"):
            result = await tool.ainvoke(tool_input)
        else:
            result = await asyncio.to_thread(tool.invoke, tool_input)
    except Exception as exc:
        logger.warning("Tool %s failed: %s", tool.name, exc)
        return f"Tool error: {exc}"

    # Cap what goes back to the model. The blast-radius tool returns the
    # full BFS result: 15 services plus every evidence path. That is 5-10
    # KB of JSON the model reads before it can even start writing the
    # reply, and it dominates latency on tool-calling turns. Trimming to
    # 3000 chars keeps the substance and drops the tail.
    TOOL_RESULT_MAX_CHARS = 3000

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
        1. Touch the session (updates timing, counts, and mood).
        2. Scan the message for mood signals and record them.
        3. Extract service names and record them as incidents.
        4. Read back the full session context.
        5. Orphan follow-up guard.
        6. Build the message list: SYSTEM_PROMPT (+ context) first, then
           history, then the current user turn.
        7. Call Groq with tools. If the model wants to call a tool,
           execute it, append the result, and call again.
        8. Return the final text and the list of tools invoked.

    Args:
        message: The user's message text.
        session_id: Unique session identifier (per tab/window).
        user_id: Stable user identifier for cross-session memory.
        history: Optional explicit history. If None, loads from memory.
        tools: Optional tools. If None, uses ALL_TOOLS.

    Returns:
        A dict with:
            - "response": Lya's text reply
            - "tool_calls": list of tool names invoked
    """
    # 1. Touch the session
    try:
        touch_session(user_id, session_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("touch_session failed: %s", exc)

    # 2. Record mood signals
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

    # 5. Load history if not provided
    if history is None:
        try:
            history = get_history(session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_history failed: %s", exc)
            history = []

    # 6. Orphan follow-up guard
    if _looks_like_orphan_followup(message, history):
        logger.info("Orphan follow-up detected — returning clarification")
        return {
            "response": _ORPHAN_REFUSAL,
            "tool_calls": [],
        }

    # 7. Build Groq messages
    if tools is None:
        tools = list(ALL_TOOLS)

    groq_messages: list[dict[str, Any]] = []

    # The system prompt is the foundation of Lya's behavior: her personality,
    # the bilingual rules, the four modes, the feminine Arabic grammar, the
    # citation style, the push-back policy. It MUST be the first message on
    # every call. The session context block is appended to it as a suffix so
    # the model reads both in a single system turn.
    system_content = SYSTEM_PROMPT
    if context_block:
        system_content = f"{SYSTEM_PROMPT}\n\n---\n\n{context_block}"
    groq_messages.append({"role": "system", "content": system_content})

    for turn in history or []:
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

    # Import Groq lazily so this module can still be imported if the SDK
    # is temporarily missing — the fallback in main.py handles that case.
    try:
        import groq as groq_sdk
    except ImportError as exc:
        logger.error("groq SDK not available: %s", exc)
        return {
            "response": "I'm not available right now. Please try again in a moment.",
            "tool_calls": [],
        }

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY missing")
        return {
            "response": "I'm not available right now. Please try again in a moment.",
            "tool_calls": [],
        }

    client = groq_sdk.Groq(api_key=api_key, timeout=GROQ_TIMEOUT, max_retries=0)
    tool_schemas = _build_tool_schemas(tools)
    tools_used: list[str] = []

    # 8. Tool-calling loop
    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=DEFAULT_MODEL,
                messages=groq_messages,
                tools=tool_schemas if tool_schemas else None,
                tool_choice="auto" if tool_schemas else None,
                temperature=DEFAULT_TEMPERATURE,
                max_tokens=MAX_TOKENS,
                reasoning_effort="low",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Groq call failed")
            return {
                "response": "I ran into a problem handling that. Please try again.",
                "tool_calls": tools_used,
                "error": str(exc),
            }

        choice = response.choices[0]
        msg = choice.message

        # No tool calls — we're done.
        if not msg.tool_calls:
            content = msg.content or ""
            # gpt-oss models sometimes put reasoning in a separate field
            # and leave content empty; fall back to reasoning if needed.
            if not content:
                reasoning = getattr(msg, "reasoning", None) or ""
                content = reasoning
            return {
                "response": content,
                "tool_calls": tools_used,
            }

        # Append the assistant message with its tool calls.
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

        # Execute each requested tool.
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

    # Exceeded max iterations.
    logger.warning("Agent loop hit max iterations (%d)", MAX_TOOL_ITERATIONS)
    return {
        "response": "I couldn't finish that request in time. Please try rephrasing.",
        "tool_calls": tools_used,
    }