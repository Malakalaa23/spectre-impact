"""
agent.py — The Lya chat agent (LangChain 1.x).

This module builds a LangChain 1.x agent using `langchain.agents.create_agent`,
which returns a compiled LangGraph. The agent uses Lya's personality
(from `chat.prompts`) and a set of tools (from `chat.tools`) to answer
developer questions about the Spectre Impact system.

By default, the agent is given every tool in `chat.tools.ALL_TOOLS`.
Callers may override this to run tool-less (useful for tests).

The agent is stateless by design. Conversation memory (Redis-backed) is
handled by a higher layer so that tests can run without a Redis connection.

Public API:
    build_agent(tools=None)  — construct a fresh agent graph.
    chat(message, ...)       — send one message, get one response back.
"""

from __future__ import annotations

import logging
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
# Groq is our primary provider — fast and cheap. Model choice is centralized
# here so we can swap it without touching agent logic.
#
# Model history:
#   - "llama-3.3-70b-versatile"  → deprecated by Groq (404 as of Sept 2026)
#   - "openai/gpt-oss-120b"      → current choice. GPT-4-class, native tool
#                                   calling, 120B params, fast on Groq's LPU.
#                                   This is the biggest model on our Groq key.
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_TEMPERATURE = 0


def _build_llm() -> ChatGroq:
    """
    Create the Groq chat model client.

    Reads GROQ_API_KEY from the environment via the shared config helper.
    Raises ValueError if the key is missing.
    """
    api_key = get_env("GROQ_API_KEY")
    return ChatGroq(
        api_key=api_key,
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
    )


def build_agent(tools: list[BaseTool] | None = None):
    """
    Construct a fresh agent graph with the given tools.

    Args:
        tools: The list of LangChain tools the agent can call.
               If None, defaults to `chat.tools.ALL_TOOLS`.
               Pass an empty list to build a tool-less agent (for tests).

    Returns:
        A compiled LangGraph agent. Invoke it with:
            await agent.ainvoke({"messages": [...]})
        where [...] is a list of LangChain message objects.
    """
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
    """
    Convert a stored history turn into the proper LangChain message type.

    LangGraph's agent expects real message objects — HumanMessage,
    AIMessage, SystemMessage — not plain dicts. Passing dicts causes the
    agent to silently drop history and behave as if the conversation
    just started.

    Args:
        turn: A dict like {"role": "user"|"assistant"|"system",
                           "content": "..."}

    Returns:
        A LangChain message object.
    """
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
):
    """
    Build the full message list for one agent invocation.

    Order:
        1. Prior turns from history (as message objects)
        2. The current user message

    The system prompt is not included here — `create_agent` injects it
    from the `system_prompt` parameter automatically.
    """
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

    Args:
        message: The user's message text.
        history: Optional list of prior messages in
                 {"role": "user"|"assistant", "content": "..."} format.
        tools:   Optional list of tools. If None, uses ALL_TOOLS.

    Returns:
        A dict with:
            - "response": Lya's text reply
            - "tool_calls": list of tool names that were invoked (may be empty)
    """
    agent = build_agent(tools)
    messages = _build_messages(message, history)

    try:
        result = await agent.ainvoke({"messages": messages})
    except Exception as exc:  # noqa: BLE001 — surface any agent error
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
    """
    Pull the final assistant text out of the LangGraph result.

    LangChain 1.x returns {"messages": [...]} where the last message is
    the assistant's reply. Its .content may be a string or a list of
    content blocks (for models that emit structured output).
    """
    messages = result.get("messages") or []
    if not messages:
        return ""

    last = messages[-1]
    content = getattr(last, "content", "")

    if isinstance(content, str):
        return content

    # Some models return a list of content blocks: [{"type": "text", "text": "..."}]
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
    """
    Collect the names of tools that were called during the agent run.

    Walks the message list, picking up any message with tool_call blocks
    or an AIMessage that carries .tool_calls.
    """
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