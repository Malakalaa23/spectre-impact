"""
memory.py — Multi-turn memory and session awareness for the Lya chat agent.

Two layers of memory:

  1. Turn history — the raw conversation (list of {"role", "content"}).
     Redis list, keyed by session_id, capped at MAX_TURNS, 1-hour TTL.

  2. Session context — the "how is this person doing" state that Lya's
     prompt reads on every turn. Includes session timing, mood signals,
     cross-session patterns, and behavior counters.

Storage model:
    Turn history:    Redis list  at key chat:{session_id}
    Session context: Redis hash  at key session_ctx:{user_id}

    The `user_id` should be stable across sessions (cookie-based). The
    `session_id` is per-tab/per-window. Turns belong to a session; context
    belongs to the user.

Fallback:
    If REDIS_URL is unset or Redis is unreachable, everything falls back
    to in-memory dicts. Fine for local dev, lost on process restart.

Public API:
    Turn history:
        save_message(session_id, role, content)
        get_history(session_id, limit=None)
        clear_session(session_id)

    Session context:
        touch_session(user_id, session_id)       -> dict
        get_session_context(user_id, session_id) -> dict
        update_session_context(user_id, **fields)
        record_mood_signal(user_id, signal)      -> dict
        record_incident(user_id, service, pr)    -> dict
        record_pushback(user_id)                 -> dict
        record_encouragement(user_id)            -> dict
        clear_user(user_id)

    Diagnostics:
        health() -> dict
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_TURNS = 20
SESSION_TTL_SECONDS = 3600
USER_CTX_TTL_SECONDS = 60 * 60 * 24  # 24 hours
KEY_PREFIX = "chat:"
CTX_PREFIX = "session_ctx:"


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------
_redis_client = None
_redis_checked = False

_fallback_turns: dict[str, list[dict[str, str]]] = {}
_fallback_ctx: dict[str, dict[str, Any]] = {}


def _get_redis():
    """Lazily connect to Redis. Cached decision. Returns None if unusable."""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client

    _redis_checked = True
    url = os.getenv("REDIS_URL")
    if not url:
        logger.info("memory: no REDIS_URL — using in-memory store")
        return None

    try:
        import redis  # type: ignore
        client = redis.from_url(url, decode_responses=True, socket_timeout=2)
        client.ping()
        _redis_client = client
        logger.info("memory: connected to Redis at %s", url)
        return client
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory: Redis unavailable (%s) — using in-memory store", exc)
        return None


# ---------------------------------------------------------------------------
# Key + encoding helpers
# ---------------------------------------------------------------------------
def _turn_key(session_id: str) -> str:
    return f"{KEY_PREFIX}{session_id}"


def _ctx_key(user_id: str) -> str:
    return f"{CTX_PREFIX}{user_id}"


def _encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _decode(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _minutes_since(iso_ts: str | None) -> float:
    if not iso_ts:
        return 0.0
    try:
        then = datetime.fromisoformat(iso_ts)
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - then
        return delta.total_seconds() / 60.0
    except (ValueError, TypeError):
        return 0.0


# ===========================================================================
# LAYER 1 — Turn history
# ===========================================================================
def _mem_save_turn(session_id: str, turn: dict[str, str]) -> None:
    history = _fallback_turns.setdefault(session_id, [])
    history.append(turn)
    if len(history) > MAX_TURNS:
        del history[:-MAX_TURNS]


def _mem_get_turns(session_id: str, limit: int | None) -> list[dict[str, str]]:
    history = _fallback_turns.get(session_id, [])
    return history[-limit:] if limit else list(history)


def save_message(session_id: str, role: str, content: str) -> None:
    """Append one turn to a session's history."""
    if not session_id or not content:
        return

    turn = {"role": role, "content": content}
    client = _get_redis()

    if client is None:
        _mem_save_turn(session_id, turn)
        return

    try:
        key = _turn_key(session_id)
        client.rpush(key, _encode(turn))
        client.ltrim(key, -MAX_TURNS, -1)
        client.expire(key, SESSION_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory: Redis save failed (%s) — falling back", exc)
        _mem_save_turn(session_id, turn)


def get_history(session_id: str, limit: int | None = None) -> list[dict[str, str]]:
    """Retrieve a session's history, oldest first."""
    if not session_id:
        return []

    client = _get_redis()
    if client is None:
        return _mem_get_turns(session_id, limit)

    try:
        key = _turn_key(session_id)
        start = -limit if limit else 0
        raw_items = client.lrange(key, start, -1)
        turns: list[dict[str, str]] = []
        for raw in raw_items:
            turn = _decode(raw)
            if isinstance(turn, dict) and "role" in turn and "content" in turn:
                turns.append({"role": turn["role"], "content": turn["content"]})
        return turns
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory: Redis read failed (%s) — falling back", exc)
        return _mem_get_turns(session_id, limit)


def clear_session(session_id: str) -> None:
    """Delete turn history for a session. Does NOT clear user context."""
    if not session_id:
        return

    client = _get_redis()
    if client is not None:
        try:
            client.delete(_turn_key(session_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory: Redis clear failed: %s", exc)

    _fallback_turns.pop(session_id, None)


# ===========================================================================
# LAYER 2 — Session context (mood, cross-session memory, behavior)
# ===========================================================================
DEFAULT_CONTEXT: dict[str, Any] = {
    "user_id": "",
    "first_seen": "",
    "last_seen": "",
    "session_count": 0,
    "active_session_id": "",
    "session_start": "",
    "turn_count": 0,
    "mood": "unknown",
    "mood_signals": [],
    "recent_incidents": [],
    "cross_session_topics": [],
    "encouragements_given": 0,
    "last_pushed_back": "",
    "language_preference": "en",
}


# ---------------------------------------------------------------------------
# Raw context readers/writers
# ---------------------------------------------------------------------------
def _mem_read_raw(user_id: str) -> dict[str, Any]:
    """Read the memory-stored context for a user, initializing if absent."""
    ctx = _fallback_ctx.get(user_id)
    if ctx is None:
        ctx = dict(DEFAULT_CONTEXT)
        ctx["user_id"] = user_id
        ctx["first_seen"] = _now_iso()
        _fallback_ctx[user_id] = ctx
    return ctx


def _mem_write_raw(user_id: str, ctx: dict[str, Any]) -> None:
    ctx["last_seen"] = _now_iso()
    _fallback_ctx[user_id] = ctx


def _redis_read_raw(client, user_id: str) -> dict[str, Any]:
    """Read the raw Redis hash for a user, decode JSON-ish fields."""
    raw = client.hgetall(_ctx_key(user_id))
    ctx = dict(DEFAULT_CONTEXT, user_id=user_id)
    if not raw:
        ctx["first_seen"] = _now_iso()
        return ctx

    for k, v in raw.items():
        if not isinstance(v, str):
            ctx[k] = v
            continue
        if v[:1] in ("[", "{", "\""):
            parsed = _decode(v)
            ctx[k] = parsed if parsed is not None else v
        else:
            ctx[k] = v

    for key in ("session_count", "turn_count", "encouragements_given"):
        try:
            ctx[key] = int(ctx.get(key, 0))
        except (ValueError, TypeError):
            ctx[key] = 0

    return ctx


def _redis_write_raw(client, user_id: str, ctx: dict[str, Any]) -> None:
    ctx["last_seen"] = _now_iso()
    key = _ctx_key(user_id)
    client.hset(key, mapping={k: _encode(v) for k, v in ctx.items()})
    client.expire(key, USER_CTX_TTL_SECONDS)


# ---------------------------------------------------------------------------
# Public context API
# ---------------------------------------------------------------------------
def get_session_context(user_id: str, session_id: str | None = None) -> dict[str, Any]:
    """
    Read the current context for a user.

    If `session_id` is given and does NOT match the active session, returns
    a fresh context (used by callers who want to know "is this the same
    session as before?"). If you want the raw stored context regardless of
    session, pass `session_id=None`.
    """
    if not user_id:
        return dict(DEFAULT_CONTEXT)

    client = _get_redis()

    if client is None:
        ctx = _mem_read_raw(user_id)
    else:
        try:
            ctx = _redis_read_raw(client, user_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory: Redis ctx read failed (%s)", exc)
            ctx = _mem_read_raw(user_id)

    if session_id and ctx.get("active_session_id") != session_id:
        # Caller is asking for a different session — return a fresh context.
        fresh = dict(DEFAULT_CONTEXT)
        fresh["user_id"] = user_id
        return fresh

    return ctx


def touch_session(user_id: str, session_id: str) -> dict[str, Any]:
    """
    Called when a user starts a turn.

    Reads the raw stored context (regardless of session), then mutates:
        - If this is a new session_id, bump session_count and reset turn_count.
        - Otherwise, increment turn_count.
    """
    if not user_id or not session_id:
        return dict(DEFAULT_CONTEXT)

    client = _get_redis()

    def _mutate(ctx: dict[str, Any]) -> dict[str, Any]:
        now = _now_iso()
        if not ctx.get("first_seen"):
            ctx["first_seen"] = now
        ctx["last_seen"] = now

        if ctx.get("active_session_id") != session_id:
            ctx["active_session_id"] = session_id
            ctx["session_start"] = now
            ctx["session_count"] = int(ctx.get("session_count", 0)) + 1
            ctx["turn_count"] = 0

        ctx["turn_count"] = int(ctx.get("turn_count", 0)) + 1
        return ctx

    if client is None:
        ctx = _mem_read_raw(user_id)
        ctx = _mutate(ctx)
        _mem_write_raw(user_id, ctx)
        return ctx

    try:
        ctx = _redis_read_raw(client, user_id)
        ctx = _mutate(ctx)
        _redis_write_raw(client, user_id, ctx)
        return ctx
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory: Redis touch failed (%s)", exc)
        ctx = _mem_read_raw(user_id)
        ctx = _mutate(ctx)
        _mem_write_raw(user_id, ctx)
        return ctx


def update_session_context(user_id: str, **fields: Any) -> dict[str, Any]:
    """Directly set context fields. Use sparingly."""
    if not user_id:
        return dict(DEFAULT_CONTEXT)

    client = _get_redis()

    if client is None:
        ctx = _mem_read_raw(user_id)
        ctx.update(fields)
        _mem_write_raw(user_id, ctx)
        return ctx

    try:
        ctx = _redis_read_raw(client, user_id)
        ctx.update(fields)
        _redis_write_raw(client, user_id, ctx)
        return ctx
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory: Redis update failed (%s)", exc)
        ctx = _mem_read_raw(user_id)
        ctx.update(fields)
        _mem_write_raw(user_id, ctx)
        return ctx


# ---------------------------------------------------------------------------
# Mood + behavior signals
# ---------------------------------------------------------------------------
MOOD_SIGNAL_WEIGHTS = {
    "all_caps": 2,
    "exclamations": 1,
    "short_message": 1,
    "long_session": 2,
    "rapid_fire": 2,
    "apology": 1,
    "vent": 3,
}

MAX_SIGNALS_KEPT = 10


def _detect_mood(signals: list[str], turn_count: int, session_minutes: float) -> str:
    """Return a coarse mood label from recent signals + session shape."""
    if not signals and session_minutes < 30:
        return "calm"
    if session_minutes > 90 and turn_count > 15:
        return "exhausted"
    score = sum(MOOD_SIGNAL_WEIGHTS.get(s, 0) for s in signals)
    if score >= 6:
        return "frustrated"
    if score >= 3:
        return "stressed"
    if session_minutes > 45:
        return "focused"
    return "calm"


def record_mood_signal(user_id: str, signal: str) -> dict[str, Any]:
    """
    Append a mood signal and recompute the mood snapshot.

    Expected signals: "all_caps", "exclamations", "short_message",
    "long_session", "rapid_fire", "apology", "vent".
    """
    if not user_id or not signal:
        return get_session_context(user_id)

    client = _get_redis()

    if client is None:
        ctx = _mem_read_raw(user_id)
    else:
        try:
            ctx = _redis_read_raw(client, user_id)
        except Exception:
            ctx = _mem_read_raw(user_id)

    signals = list(ctx.get("mood_signals") or [])
    signals.append(signal)
    signals = signals[-MAX_SIGNALS_KEPT:]

    session_minutes = _minutes_since(ctx.get("session_start"))
    mood = _detect_mood(signals, int(ctx.get("turn_count", 0)), session_minutes)

    return update_session_context(
        user_id,
        mood_signals=signals,
        mood=mood,
    )


def record_incident(user_id: str, service: str, pr: int | None = None) -> dict[str, Any]:
    """Record an incident or query about a service/PR in recent history."""
    if not user_id:
        return get_session_context(user_id)

    entry = {"service": service, "pr": pr, "ts": _now_iso()}

    client = _get_redis()
    if client is None:
        ctx = _mem_read_raw(user_id)
    else:
        try:
            ctx = _redis_read_raw(client, user_id)
        except Exception:
            ctx = _mem_read_raw(user_id)

    incidents = list(ctx.get("recent_incidents") or [])
    incidents.append(entry)
    incidents = incidents[-20:]

    topic_counter: dict[str, int] = {}
    for inc in incidents:
        topic_counter[inc["service"]] = topic_counter.get(inc["service"], 0) + 1
    recurring = sorted(
        [s for s, c in topic_counter.items() if c >= 3],
        key=lambda s: -topic_counter[s],
    )[:5]

    return update_session_context(
        user_id,
        recent_incidents=incidents,
        cross_session_topics=recurring,
    )


def record_pushback(user_id: str) -> dict[str, Any]:
    """Note that Lya just disagreed with the engineer."""
    return update_session_context(user_id, last_pushed_back=_now_iso())


def record_encouragement(user_id: str) -> dict[str, Any]:
    """Increment the encouragement counter."""
    ctx = get_session_context(user_id)
    count = int(ctx.get("encouragements_given", 0)) + 1
    return update_session_context(user_id, encouragements_given=count)


def clear_user(user_id: str) -> None:
    """Delete all context for a user. Does NOT touch turn history."""
    if not user_id:
        return

    client = _get_redis()
    if client is not None:
        try:
            client.delete(_ctx_key(user_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory: Redis clear_user failed: %s", exc)

    _fallback_ctx.pop(user_id, None)


# ===========================================================================
# Diagnostics
# ===========================================================================
def health() -> dict[str, Any]:
    """Report on the memory backend."""
    client = _get_redis()
    if client is None:
        return {
            "backend": "in-memory",
            "sessions": len(_fallback_turns),
            "users": len(_fallback_ctx),
            "max_turns": MAX_TURNS,
        }
    return {
        "backend": "redis",
        "sessions": "unknown",
        "users": "unknown",
        "max_turns": MAX_TURNS,
    }


__all__ = [
    "save_message",
    "get_history",
    "clear_session",
    "touch_session",
    "get_session_context",
    "update_session_context",
    "record_mood_signal",
    "record_incident",
    "record_pushback",
    "record_encouragement",
    "clear_user",
    "health",
]