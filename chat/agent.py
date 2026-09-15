"""
agent.py — The Lya chat agent (LangChain 1.x).

Builds a LangChain 1.x agent using `langchain.agents.create_agent`, which
returns a compiled LangGraph. The agent uses Lya's personality (from
`chat.prompts`) and the tools from `chat.tools`.

Runtime guard:
    Before invoking the LLM, `chat()` checks whether the user's message
    looks like an orphan follow-up — a short question that references
    prior context ("those", "that", "which of them") — while the session
    has no history. If so, it returns a clarification request without
    calling the LLM. This guarantees the behavior even if the model
    would otherwise answer from generic knowledge.

Public API:
    build_agent(tools=None)  — construct a fresh agent graph.
    chat(message, ...)       — send one message, get one response back.
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
# The pattern catches short messages that clearly reference prior context
# while the session has no history. We deliberately err on the side of
# NOT triggering — false negatives are better than false positives.
#
# Triggers when ALL of these hold:
#   1. No conversation history in the session.
#   2. The message has ≤ 20 words (short).
#   3. The message contains at least one referential word or phrase.

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


def _looks_like_orphan_followup(message: str, history: list[dict[str, Any]] | None) -> bool:
    """
    Return True if the message looks like an orphan follow-up.

    An orphan follow-up is a short question that references prior context
    ("those", "them", "that") while the session has no history. In that
    case, the correct response is to ask for clarification, not to invent
    an answer.
    """
    if history:
        return False  # session has context, don't block

    text = (message or "").strip()
    if not text:
        return False

    # Short messages only
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


def _build_messages(message: str, history: list[dict[str, Any]] | None):
    """Build the message list for one agent invocation."""
    messages = []
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
    history: list[dict[str, Any]] | None = None,
    tools: list[BaseTool] | None = None,
) -> dict[str, Any]:
    """
    Send one message to Lya and return her response.

    Includes a runtime guard: if the message looks like an orphan
    follow-up (references prior context, but history is empty), the
    guard returns a clarification request without invoking the LLM.
    """
    # Runtime guard — catch orphan follow-ups before they reach the LLM
    if _looks_like_orphan_followup(message, history):
        logger.info("Orphan follow-up detected — returning clarification")
        return {
            "response": _ORPHAN_REFUSAL,
            "tool_calls": [],
        }

    agent = build_agent(tools)
    messages = _build_messages(message, history)

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