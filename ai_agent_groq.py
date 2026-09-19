"""AI provider abstraction with Groq -> OpenAI -> Anthropic fallback.

The module is intentionally dependency-light: providers are imported only when
needed, so the deterministic impact engine still works without API keys.
"""
from __future__ import annotations

import json
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from dataclasses import dataclass
from typing import Any

SYSTEM_PROMPT = """You are Alex — a Senior Backend Engineer and AI collaborator for Spectre Impact.
Be direct, focused, and practical. Explain technical risk from evidence in the
provided context. Never invent repository facts. Prefer concise actionable
recommendations and explicitly distinguish deterministic analysis from AI advice.
"""


@dataclass
class AIResponse:
    text: str
    provider: str
    model: str


def _provider_order() -> list[str]:
    configured = os.getenv("SPECTRE_AI_PROVIDERS", "groq,openai,anthropic")
    return [p.strip().lower() for p in configured.split(",") if p.strip()]


def _groq(prompt: str, *, system: str = SYSTEM_PROMPT) -> AIResponse:
    from groq import Groq

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return AIResponse(response.choices[0].message.content or "", "groq", model)


def _openai(prompt: str, *, system: str = SYSTEM_PROMPT) -> AIResponse:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return AIResponse(response.choices[0].message.content or "", "openai", model)


def _anthropic(prompt: str, *, system: str = SYSTEM_PROMPT) -> AIResponse:
    from anthropic import Anthropic

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    response = client.messages.create(
        model=model,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
    return AIResponse(text, "anthropic", model)


def generate_text(prompt: str, *, system: str = SYSTEM_PROMPT) -> AIResponse:
    """Generate text using the first configured provider that succeeds."""
    errors: list[str] = []
    providers = {"groq": _groq, "openai": _openai, "anthropic": _anthropic}
    for name in _provider_order():
        if name not in providers:
            continue
        key_name = {"groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}[name]
        if not os.getenv(key_name):
            errors.append(f"{name}: missing {key_name}")
            continue
        try:
            return providers[name](prompt, system=system)
        except Exception as exc:  # provider fallback is deliberate
            errors.append(f"{name}: {exc}")
    raise RuntimeError("No AI provider succeeded. " + " | ".join(errors))


def generate_insights(affected_services: list[str], business_impact: int, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return structured-ish AI deployment guidance while remaining JSON friendly."""
    payload = {
        "affected_services": affected_services,
        "business_impact": business_impact,
        "context": context or {},
    }
    prompt = """Analyze this Spectre Impact result. Return exactly these four headings:
Severity:
Simulation:
Rollback:
Validation:
Keep each section short and grounded in the supplied data.

DATA:\n""" + json.dumps(payload, indent=2)
    try:
        response = generate_text(prompt)
        text = response.text
    except Exception as exc:
        return {
            "severity": "AI unavailable",
            "simulation": "Deterministic analysis is still valid; no AI simulation was generated.",
            "rollback": "Follow the deterministic rollback_required flag.",
            "validation": "Run the repository test suite and service-specific smoke tests.",
            "provider": None,
            "error": str(exc),
        }

    sections = {"severity": "", "simulation": "", "rollback": "", "validation": ""}
    current = None
    aliases = {"severity": "severity", "simulation": "simulation", "rollback": "rollback", "validation": "validation"}
    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower().rstrip(":")
        matched = next((k for k in aliases if lower.startswith(k)), None)
        if matched:
            current = matched
            remainder = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            sections[current] = remainder
        elif current and stripped:
            sections[current] += (" " if sections[current] else "") + stripped
    sections["raw"] = text
    sections["provider"] = response.provider
    sections["model"] = response.model
    return sections
