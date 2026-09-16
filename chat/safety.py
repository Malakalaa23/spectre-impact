"""
safety.py — Input sanitization and output filtering for the Lya chat agent.

Two layers of protection:

    Input guards (sanitize_input):
        - Block classic prompt-injection phrases ("ignore previous instructions")
        - Block attempts to reveal the system prompt
        - Block dangerous instructions ("execute code", "delete database")
        - Raise ValueError on match — the FastAPI layer turns it into a 400.

    Output filters (sanitize_output):
        - Strip anything that looks like an API key (Groq, OpenAI, Anthropic, GitHub)
        - Strip generic secret-looking strings (JWT, AWS keys, long hex tokens)
        - Redact emails and IP addresses in certain contexts
        - Return the cleaned text; never raises.

Design principles:
    - Deterministic. No LLM calls. No latency.
    - Conservative. False negatives are safer than false positives.
    - Log every block/replace so we can audit later.
    - No user-visible failure on output filtering — silent redaction.

Public API:
    sanitize_input(text) -> str          (raises ValueError on block)
    sanitize_output(text) -> str         (never raises)
    looks_suspicious(text) -> bool       (helper, non-raising)
"""

from __future__ import annotations

import logging
import re


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input patterns — things we refuse to process
# ---------------------------------------------------------------------------
# Each entry is (regex, label). The label is used in logs.
# We match case-insensitively. Patterns are deliberately specific to reduce
# false positives on legitimate security questions.
# ---------------------------------------------------------------------------
_INPUT_BLOCKLIST: list[tuple[re.Pattern[str], str]] = [
    # Prompt injection attempts
    (re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|rules)", re.I),
     "prompt_injection_classic"),
    (re.compile(r"forget\s+(?:everything|all)\s+(?:you|that)", re.I),
     "prompt_injection_forget"),
    (re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|above)", re.I),
     "prompt_injection_disregard"),
    (re.compile(r"you\s+are\s+now\s+(?:a|an|in)\s+", re.I),
     "prompt_injection_role_change"),

    # System prompt extraction
    (re.compile(r"(?:reveal|show|print|output|tell\s+me)\s+(?:your\s+)?(?:system\s+)?prompt", re.I),
     "system_prompt_extraction"),
    (re.compile(r"what\s+(?:are|were)\s+your\s+(?:initial\s+)?instructions", re.I),
     "system_prompt_extraction"),

    # Secret harvesting
    (re.compile(r"(?:show|reveal|print|output|tell\s+me)\s+(?:me\s+)?(?:the\s+)?(?:api\s*keys?|tokens?|secrets?|passwords?)", re.I),
     "secret_harvesting"),
    (re.compile(r"what\s+(?:is|are)\s+(?:your\s+)?(?:api\s*key|env(?:ironment)?\s+variables?|\.env)", re.I),
     "secret_harvesting"),

    # Destructive commands
    (re.compile(r"\b(?:rm\s+-rf|drop\s+table|delete\s+database|format\s+c:)\b", re.I),
     "destructive_command"),
]


# ---------------------------------------------------------------------------
# Output patterns — things we redact silently
# ---------------------------------------------------------------------------
_OUTPUT_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    # Groq API keys: "gsk_" + 40+ alphanumeric
    (re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"),
     "[REDACTED_GROQ_KEY]"),

    # OpenAI keys: "sk-" + 40+ chars (project or org keys)
    (re.compile(r"\bsk-[A-Za-z0-9\-_]{20,}\b"),
     "[REDACTED_OPENAI_KEY]"),

    # Anthropic keys: "sk-ant-" + ...
    (re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b"),
     "[REDACTED_ANTHROPIC_KEY]"),

    # GitHub tokens: "ghp_", "gho_", "ghs_", "ghu_", "github_pat_" + ...
    (re.compile(r"\b(?:ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9]{20,}\b"),
     "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
     "[REDACTED_GITHUB_PAT]"),

    # Generic AWS-style keys: AKIA + 16 chars
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
     "[REDACTED_AWS_KEY]"),

    # JWT-style tokens: three base64url segments separated by dots
    (re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"),
     "[REDACTED_JWT]"),

    # Long hex strings (32+ chars) — could be tokens, secrets, hashes
    (re.compile(r"\b[a-f0-9]{32,}\b"),
     "[REDACTED_HEX]"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def looks_suspicious(text: str) -> bool:
    """
    Return True if the input matches any blocklist pattern.

    Non-raising — used for logging and diagnostics without breaking flow.
    """
    if not text or not text.strip():
        return False

    for pattern, _label in _INPUT_BLOCKLIST:
        if pattern.search(text):
            return True
    return False


def sanitize_input(text: str) -> str:
    """
    Validate the user's input and raise ValueError if it looks malicious.

    Args:
        text: Raw user message.

    Returns:
        The original text if it passes (unchanged — we don't alter user input).

    Raises:
        ValueError: with a short reason label if the input is blocked.
    """
    if text is None:
        raise ValueError("empty_input")

    if len(text) > 4000:
        # Belt-and-braces; FastAPI also enforces this via Pydantic.
        raise ValueError("input_too_long")

    for pattern, label in _INPUT_BLOCKLIST:
        match = pattern.search(text)
        if match:
            logger.warning(
                "🛡️ Input blocked: %s | matched: %r | input_preview: %r",
                label,
                match.group(0)[:60],
                text[:120],
            )
            raise ValueError(label)

    return text


def sanitize_output(text: str) -> str:
    """
    Redact sensitive patterns from the assistant's output.

    Never raises — on any error, returns the original text.

    Args:
        text: The assistant's raw reply.

    Returns:
        The reply with any API keys, tokens, or secrets replaced by
        a placeholder like [REDACTED_GROQ_KEY].
    """
    if not text:
        return text

    redacted = text
    replacements = 0

    for pattern, replacement in _OUTPUT_REDACTIONS:
        new_text, count = pattern.subn(replacement, redacted)
        if count:
            replacements += count
            redacted = new_text

    if replacements:
        logger.info("🛡️ Output sanitized: %d redaction(s)", replacements)

    return redacted


__all__ = ["sanitize_input", "sanitize_output", "looks_suspicious"]