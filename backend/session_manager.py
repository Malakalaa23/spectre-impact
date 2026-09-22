"""Crash-resistant, user-isolated chat session storage.

Redis is used when REDIS_URL is configured. A bounded in-process store is the
fallback for local development; it is deliberately TTL-bound and thread-safe.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from collections import OrderedDict
from typing import Any


class SessionManager:
    def __init__(self, ttl_seconds: int = 3600, max_sessions: int = 1000):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._lock = threading.RLock()
        self._local: OrderedDict[str, tuple[float, list[dict[str, str]]]] = OrderedDict()
        self._redis = None
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis
                self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None

    @property
    def backend(self) -> str:
        return "redis" if self._redis is not None else "memory"

    def create(self) -> str:
        session_id = uuid.uuid4().hex
        self._write(session_id, [])
        return session_id

    def get(self, session_id: str) -> list[dict[str, str]]:
        if self._redis is not None:
            raw = self._redis.get(self._key(session_id))
            return json.loads(raw) if raw else []
        with self._lock:
            self._cleanup()
            row = self._local.get(session_id)
            if not row:
                return []
            expires, messages = row
            self._local.move_to_end(session_id)
            return list(messages) if expires > time.time() else []

    def append(self, session_id: str, role: str, content: str) -> None:
        messages = self.get(session_id)
        messages.append({"role": role, "content": content})
        messages = messages[-20:]
        self._write(session_id, messages)

    def _key(self, session_id: str) -> str:
        return f"spectre:session:{session_id}"

    def _write(self, session_id: str, messages: list[dict[str, str]]) -> None:
        if self._redis is not None:
            self._redis.setex(self._key(session_id), self.ttl_seconds, json.dumps(messages))
            return
        with self._lock:
            self._cleanup()
            self._local[session_id] = (time.time() + self.ttl_seconds, list(messages))
            self._local.move_to_end(session_id)
            while len(self._local) > self.max_sessions:
                self._local.popitem(last=False)

    def _cleanup(self) -> None:
        now = time.time()
        expired = [key for key, (expires, _) in self._local.items() if expires <= now]
        for key in expired:
            self._local.pop(key, None)


sessions = SessionManager()
