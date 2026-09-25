"""
api_client.py — Thin HTTP client for the Spectre Impact FastAPI backend.

The Streamlit frontend runs in the same Docker container as FastAPI, so
it must talk to the backend via localhost on the internal port (8000),
NOT via a public Render URL.

Environment:
    BACKEND_URL — override the default. Defaults to http://localhost:8000.
"""

from __future__ import annotations

import os
from typing import Any

import requests


# FastAPI is started on port 8000 by start.sh (internal to the container).
# Streamlit talks to it locally. Do NOT point this at a public URL.
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

DEFAULT_TIMEOUT = 15


def get_json_detailed(endpoint: str, timeout: int = DEFAULT_TIMEOUT):
    """
    GET a JSON endpoint on the backend.

    Returns:
        (ok, data, error) — a three-tuple. `ok` is True on success.
        On failure, `data` is None and `error` is a human-readable string.
    """
    url = f"{BACKEND_URL}{endpoint}"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        try:
            return True, response.json(), None
        except ValueError as exc:
            return False, None, f"Invalid JSON from {endpoint}: {exc}"
    except requests.exceptions.Timeout:
        return False, None, f"Timeout after {timeout}s calling {endpoint}"
    except requests.exceptions.ConnectionError as exc:
        return False, None, f"Backend unreachable at {url}: {exc}"
    except requests.exceptions.HTTPError as exc:
        return False, None, f"HTTP {exc.response.status_code} from {endpoint}"
    except Exception as exc:  # noqa: BLE001
        return False, None, f"Unexpected error calling {endpoint}: {exc}"


def get_json(endpoint: str, timeout: int = DEFAULT_TIMEOUT) -> Any | None:
    """Convenience: return parsed JSON or None."""
    ok, data, _ = get_json_detailed(endpoint, timeout=timeout)
    return data if ok else None


def post_json(endpoint: str, payload: dict, timeout: int = DEFAULT_TIMEOUT):
    """POST JSON to the backend. Returns (ok, data, error)."""
    url = f"{BACKEND_URL}{endpoint}"
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        try:
            return True, response.json(), None
        except ValueError:
            return True, response.text, None
    except requests.exceptions.HTTPError as exc:
        body = ""
        try:
            body = exc.response.text[:500]
        except Exception:
            pass
        return False, None, f"HTTP {exc.response.status_code}: {body}"
    except Exception as exc:  # noqa: BLE001
        return False, None, f"POST {endpoint} failed: {exc}"