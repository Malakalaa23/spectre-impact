"""
multi_provider.py — Multi-provider AI fallback chain for Spectre Impact.

Provides a single function `call_ai(prompt, **kwargs)` that tries a chain
of LLM providers in order, returning the first successful response.

Provider chain (configurable at runtime):
    1. Groq      — primary. Fast, cheap, high throughput.
                   Tries a large model first, then a small model on 429.
    2. Google    — first fallback. Free tier, reliable, no credit card.
    3. OpenAI    — second fallback. Reliable, more expensive.
    4. Anthropic — third fallback. Excellent reasoning, slower.
    5. Fallback  — deterministic response if all providers fail.

Design principles:
    - Never raise. Always return a valid dict.
    - Try in order. Stop at first success.
    - Log every attempt and its outcome.
    - Track which provider served the request.
    - Self-load .env so the module works in any context (scripts, tests,
      workers, the FastAPI server) without requiring the caller to
      initialize environment variables first.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv


# Load .env once, at import time. Safe no-op if the file is missing.
load_dotenv()


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Groq models are tried in order. The second is a smaller, faster model
# that is less likely to hit token-per-minute rate limits.
GROQ_MODELS: list[str] = [
    "openai/gpt-oss-120b",
    "llama3-8b-8192",
]

DEFAULT_MODELS: dict[str, str] = {
    "groq": GROQ_MODELS[0],  # primary
    "google": "gemini-1.5-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-haiku-20240307",
}

DEFAULT_MAX_TOKENS = 800
DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class ModelResult:
    """Structured result of a successful AI call."""
    provider: str
    model: str
    text: str
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "text": self.text,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Lazy client initialization
# ---------------------------------------------------------------------------
_clients: dict[str, Any] = {}


def _get_groq_client():
    """Lazily initialize the Groq client."""
    if "groq" in _clients:
        return _clients["groq"]
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        _clients["groq"] = None
        return None
    try:
        from groq import Groq
        _clients["groq"] = Groq(api_key=api_key)
        return _clients["groq"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Groq client init failed: %s", exc)
        _clients["groq"] = None
        return None


def _get_google_client():
    """Lazily initialize the Google Gemini client (global config)."""
    if "google" in _clients:
        return _clients["google"]
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        _clients["google"] = None
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        _clients["google"] = genai
        return _clients["google"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google client init failed: %s", exc)
        _clients["google"] = None
        return None


def _get_openai_client():
    """Lazily initialize the OpenAI client."""
    if "openai" in _clients:
        return _clients["openai"]
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        _clients["openai"] = None
        return None
    try:
        from openai import OpenAI
        _clients["openai"] = OpenAI(api_key=api_key)
        return _clients["openai"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI client init failed: %s", exc)
        _clients["openai"] = None
        return None


def _get_anthropic_client():
    """Lazily initialize the Anthropic client."""
    if "anthropic" in _clients:
        return _clients["anthropic"]
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        _clients["anthropic"] = None
        return None
    try:
        from anthropic import Anthropic
        _clients["anthropic"] = Anthropic(api_key=api_key)
        return _clients["anthropic"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Anthropic client init failed: %s", exc)
        _clients["anthropic"] = None
        return None


# ---------------------------------------------------------------------------
# Per-provider call functions (sync)
# ---------------------------------------------------------------------------
def _call_groq(prompt: str, max_tokens: int, temperature: float) -> ModelResult:
    """
    Call Groq, trying multiple models in order.
    Raises on any error if all models fail.
    """
    client = _get_groq_client()
    if client is None:
        raise RuntimeError("Groq client unavailable")

    last_error: Exception | None = None

    for model in GROQ_MODELS:
        try:
            start = time.monotonic()
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=DEFAULT_TIMEOUT,
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            text = response.choices[0].message.content or ""

            usage = getattr(response, "usage", None)
            return ModelResult(
                provider="groq",
                model=model,
                text=text,
                latency_ms=latency_ms,
                input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            # Only retry with a smaller model if this looks like a rate limit.
            if "429" in str(exc) or "rate limit" in str(exc).lower():
                logger.warning("Groq model %s hit rate limit, trying next...", model)
                continue
            # Any other error is fatal for Groq; move to next provider.
            break

    # If we get here, all Groq models failed.
    raise RuntimeError(f"Groq models exhausted: {last_error}")


def _call_google(prompt: str, max_tokens: int, temperature: float) -> ModelResult:
    """Call Google Gemini and return a ModelResult. Raises on any error."""
    genai = _get_google_client()
    if genai is None:
        raise RuntimeError("Google client unavailable")

    model_name = DEFAULT_MODELS["google"]
    start = time.monotonic()

    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        prompt,
        generation_config={
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        },
        request_options={"timeout": DEFAULT_TIMEOUT},
    )

    latency_ms = int((time.monotonic() - start) * 1000)
    text = response.text or ""

    return ModelResult(
        provider="google",
        model=model_name,
        text=text,
        latency_ms=latency_ms,
    )


def _call_openai(prompt: str, max_tokens: int, temperature: float) -> ModelResult:
    """Call OpenAI and return a ModelResult. Raises on any error."""
    client = _get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI client unavailable")

    model = DEFAULT_MODELS["openai"]
    start = time.monotonic()

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=DEFAULT_TIMEOUT,
    )

    latency_ms = int((time.monotonic() - start) * 1000)
    text = response.choices[0].message.content or ""

    usage = getattr(response, "usage", None)
    return ModelResult(
        provider="openai",
        model=model,
        text=text,
        latency_ms=latency_ms,
        input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
        output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
    )


def _call_anthropic(prompt: str, max_tokens: int, temperature: float) -> ModelResult:
    """Call Anthropic and return a ModelResult. Raises on any error."""
    client = _get_anthropic_client()
    if client is None:
        raise RuntimeError("Anthropic client unavailable")

    model = DEFAULT_MODELS["anthropic"]
    start = time.monotonic()

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
        timeout=DEFAULT_TIMEOUT,
    )

    latency_ms = int((time.monotonic() - start) * 1000)

    text_parts: list[str] = []
    for block in response.content or []:
        block_text = getattr(block, "text", None)
        if block_text:
            text_parts.append(block_text)
    text = "".join(text_parts)

    usage = getattr(response, "usage", None)
    return ModelResult(
        provider="anthropic",
        model=model,
        text=text,
        latency_ms=latency_ms,
        input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
        output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
    )


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------
_PROVIDERS: list[tuple[str, Any]] = [
    ("groq", _call_groq),
    ("google", _call_google),
    ("openai", _call_openai),
    ("anthropic", _call_anthropic),
]


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------
def _deterministic_fallback(reason: str = "all_providers_failed") -> ModelResult:
    """
    Return a safe, deterministic response when every provider fails.

    Production systems never fail silently. They return something the
    caller can handle.
    """
    return ModelResult(
        provider="fallback",
        model="none",
        text=(
            "The AI service is temporarily unavailable. "
            "Please try again in a moment, or review this change manually. "
            "All other Spectre Impact features remain available."
        ),
        latency_ms=0,
        metadata={"reason": reason},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def call_ai(
    prompt: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    providers: list[str] | None = None,
) -> dict[str, Any]:
    """
    Try each provider in order; return the first successful response.

    Args:
        prompt: The user-facing prompt text.
        max_tokens: Max tokens for the response.
        temperature: Sampling temperature.
        providers: Optional subset of provider names to try, in order.
                   Defaults to ["groq", "google", "openai", "anthropic"].

    Returns:
        A dict with provider, model, text, latency_ms, tokens, metadata.
        Never raises — falls back to a deterministic response.
    """
    if not prompt or not prompt.strip():
        return _deterministic_fallback("empty_prompt").to_dict()

    requested = providers or [name for name, _ in _PROVIDERS]
    chain = [(name, fn) for name, fn in _PROVIDERS if name in requested]

    if not chain:
        logger.warning("No valid providers in chain: %r", requested)
        return _deterministic_fallback("no_providers").to_dict()

    errors: list[str] = []

    for name, call_fn in chain:
        try:
            logger.info("Trying provider: %s", name)
            result = call_fn(prompt, max_tokens, temperature)
            if not result.text.strip():
                raise RuntimeError("empty response")
            logger.info(
                "✅ Provider %s succeeded (%d ms, %d out tokens)",
                name, result.latency_ms, result.output_tokens,
            )
            return result.to_dict()
        except Exception as exc:  # noqa: BLE001
            logger.warning("❌ Provider %s failed: %s", name, exc)
            errors.append(f"{name}: {exc}")

    logger.error("All providers failed: %s", " | ".join(errors))
    result = _deterministic_fallback("all_providers_failed")
    result.metadata["errors"] = errors
    return result.to_dict()


async def call_ai_async(
    prompt: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    providers: list[str] | None = None,
) -> dict[str, Any]:
    """
    Async wrapper around call_ai.

    Runs the sync call in a thread so it doesn't block the event loop.
    """
    import asyncio

    return await asyncio.to_thread(
        call_ai,
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        providers=providers,
    )


def provider_status() -> dict[str, Any]:
    """
    Report the availability of each provider based on env keys.

    Does NOT make network calls — just checks if the API key is set
    and a client can be constructed.
    """
    status: dict[str, Any] = {"chain": [name for name, _ in _PROVIDERS]}

    for name in ("groq", "google", "openai", "anthropic"):
        env_var = f"{name.upper()}_API_KEY"
        has_key = bool(os.getenv(env_var))
        status[name] = {
            "env_var": env_var,
            "key_set": has_key,
            "available": False,
        }

    if _get_groq_client() is not None:
        status["groq"]["available"] = True
    if _get_google_client() is not None:
        status["google"]["available"] = True
    if _get_openai_client() is not None:
        status["openai"]["available"] = True
    if _get_anthropic_client() is not None:
        status["anthropic"]["available"] = True

    return status


__all__ = [
    "call_ai",
    "call_ai_async",
    "provider_status",
    "ModelResult",
    "DEFAULT_MODELS",
]