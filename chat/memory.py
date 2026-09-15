"""
memory.py — Multi-turn memory for the Lya chat agent.

Stores the conversation history for each session so Lya can remember
what was said earlier. Uses Redis as the primary backend, with an
in-memory fallback so development works without Redis running.

Storage model:
    Each session is a Redis list keyed by "chat:{session_id}".
    Each list element is a JSON-encoded turn:
        {"role": "user"|"assistant", "content": "..."}
    Lists are trimmed to the most recent MAX_TURNS entries.
    Keys expire after SESSION_TTL_SECONDS of inactivity.

Fallback:
    If REDIS_URL is missing or Redis is unreachable, memory is stored
    in a module-level dict. This is fine for local dev but does NOT
    survive process restarts.

Public API:
    get_history(session_id, limit)   -> list of turns
    save_message(session_id, role, content)
    clear_session(session_id)
    health() -> dict
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_TURNS = 20               # keep the most recent N turns per session
SESSION_TTL_SECONDS = 3600   # 1 hour of inactivity before the key expires
KEY_PREFIX = "chat:"


# ---------------------------------------------------------------------------
# Backend selection — Redis if available, in-memory otherwise
# ---------------------------------------------------------------------------
_redis_client = None
_fallback_store: dict[str, list[dict[str, str]]] = {}


def _get_redis():
    """
    Lazily connect to Redis. Returns None if unavailable.

    Reads REDIS_URL from the environment. If missing or connection fails,
    returns None so callers fall back to in-memory storage.
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    url = os.getenv("REDIS_URL")
    if not url:
        logger.info("REDIS_URL not set — using in-memory memory store")
        return None

    try:
        import redis  # type: ignore

        client = redis.from_url(url, decode_responses=True, socket_timeout=2)
        client.ping()
        _redis_client = client
        logger.info("Connected to Redis at %s", url)
        return client
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis connection failed: %s — using in-memory store", exc)
        return None


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------
def _key(session_id: str) -> str:
    """Build the Redis key for a session."""
    return f"{KEY_PREFIX}{session_id}"


def _encode(turn: dict[str, str]) -> str:
    """JSON-encode a turn for storage."""
    return json.dumps(turn, ensure_ascii=False)


def _decode(raw: str) -> dict[str, str] | None:
    """JSON-decode a turn from storage. Returns None if malformed."""
    try:
        turn = json.loads(raw)
        if isinstance(turn, dict) and "role" in turn and "content" in turn:
            return {"role": turn["role"], "content": turn["content"]}
    except (json.JSONDecodeError, TypeError):
        pass
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def save_message(session_id: str, role: str, content: str) -> None:
    """
    Append one message to a session's history.

    Args:
        session_id: Unique session identifier (e.g. user UUID).
        role:       "user", "assistant", or "system".
        content:    The message text. Stored as-is (UTF-8).
    """
    if not session_id or not content:
        return

    turn = {"role": role, "content": content}
    client = _get_redis()

    if client is not None:
        try:
            key = _key(session_id)
            client.rpush(key, _encode(turn))
            client.ltrim(key, -MAX_TURNS, -1)
            client.expire(key, SESSION_TTL_SECONDS)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis save failed, falling back to memory: %s", exc)
            _save_fallback(session_id, turn)
    else:
        _save_fallback(session_id, turn)


def _save_fallback(session_id: str, turn: dict[str, str]) -> None:
    """In-memory fallback used when Redis is unavailable."""
    history = _fallback_store.setdefault(session_id, [])
    history.append(turn)
    if len(history) > MAX_TURNS:
        del history[:-MAX_TURNS]


def get_history(session_id: str, limit: int | None = None) -> list[dict[str, str]]:
    """
    Retrieve a session's conversation history, oldest first.

    Args:
        session_id: Unique session identifier.
        limit:      Optional max number of turns to return (most recent).

    Returns:
        A list of {"role": ..., "content": ...} dicts. Empty if no history.
    """
    if not session_id:
        return []

    client = _get_redis()
    turns: list[dict[str, str]] = []

    if client is not None:
        try:
            key = _key(session_id)
            start = -limit if limit else 0
            raw_items = client.lrange(key, start, -1)
            for raw in raw_items:
                turn = _decode(raw)
                if turn:
                    turns.append(turn)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis read failed, using fallback: %s", exc)
            turns = _get_fallback(session_id, limit)
    else:
        turns = _get_fallback(session_id, limit)

    return turns


def _get_fallback(session_id: str, limit: int | None) -> list[dict[str, str]]:
    """In-memory fallback read."""
    history = _fallback_store.get(session_id, [])
    return history[-limit:] if limit else list(history)


def clear_session(session_id: str) -> None:
    """
    Delete all history for a session.

    Called on logout or when the user explicitly resets the conversation.
    """
    if not session_id:
        return

    client = _get_redis()
    if client is not None:
        try:
            client.delete(_key(session_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis delete failed: %s", exc)

    _fallback_store.pop(session_id, None)


def health() -> dict[str, Any]:
    """
    Report on the memory backend's health.

    Useful for /health endpoints and debugging.
    """
    client = _get_redis()
    if client is None:
        return {
            "backend": "in-memory",
            "sessions": len(_fallback_store),
            "max_turns": MAX_TURNS,
            "ttl_seconds": None,
        }
    return {
        "backend": "redis",
        "sessions": "unknown",  # querying would be O(N)
        "max_turns": MAX_TURNS,
        "ttl_seconds": SESSION_TTL_SECONDS,
    }


__all__ = ["get_history", "save_message", "clear_session", "health"]