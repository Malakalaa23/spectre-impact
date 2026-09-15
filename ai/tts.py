"""
tts.py — Text-to-Speech for the Lya chat agent.

Provides a unified `synthesize()` function that converts text into MP3
audio bytes. Uses Microsoft Edge TTS (free, high quality).

Voices:
    - ar-EG-SalmaNeural   (Egyptian Arabic, female)   ← default for Lya (Arabic)
    - ar-EG-ShakirNeural  (Egyptian Arabic, male)
    - en-US-AriaNeural    (English, female)           ← default for Lya (English)
    - en-US-GuyNeural     (English, male)

Prosody tuning:
    Edge TTS neural voices are clear but can sound monotone. To make them
    feel more natural, we adjust two parameters:

        rate  — speaking speed.
                Arabic: -10% (Egyptian conversational speech is slower than MSA)
                English: 0% (natural pace; earlier -5% felt sluggish)

        pitch — voice frequency. Slight upward shift adds warmth without
                sounding artificial.

    These values are stored per-voice in VOICE_PROSODY so they can be
    tweaked independently without touching synthesis code.

Design:
    - Auto-detects language from the text (Arabic script vs Latin).
    - Picks the right voice + prosody for the language.
    - Returns raw MP3 bytes ready to stream to a browser or save to disk.

Public API:
    synthesize(text, language="auto", voice=None) -> bytes
    synthesize_async(text, language="auto", voice=None) -> bytes
    detect_language(text) -> "ar" | "en"
    list_voices() -> dict
"""

from __future__ import annotations

import io
import logging
import re
from typing import Literal

import edge_tts


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Voice catalog
# ---------------------------------------------------------------------------
# Maps internal names → Edge TTS voice IDs.
EDGE_VOICES: dict[str, str] = {
    "ar-eg-female": "ar-EG-SalmaNeural",
    "ar-eg-male": "ar-EG-ShakirNeural",
    "en-us-female": "en-US-AriaNeural",
    "en-us-male": "en-US-GuyNeural",
}


# ---------------------------------------------------------------------------
# Prosody tuning per voice
# ---------------------------------------------------------------------------
# rate:  "+10%" = faster, "-10%" = slower. "+0%" = natural.
# pitch: "+5Hz" = higher, "-5Hz" = lower.    "+0Hz" = natural.
#
# Arabic female keeps a slight slowdown for warmth.
# English both keep natural pace — earlier slowdown felt sluggish.
VOICE_PROSODY: dict[str, dict[str, str]] = {
    "ar-eg-female": {"rate": "-10%", "pitch": "+5Hz"},
    "ar-eg-male":   {"rate": "-8%",  "pitch": "+2Hz"},
    "en-us-female": {"rate": "+0%",  "pitch": "+0Hz"},
    "en-us-male":   {"rate": "+0%",  "pitch": "+0Hz"},
}


# Default voice per language. Female for both — Lya is a woman.
DEFAULT_VOICE_BY_LANG: dict[str, str] = {
    "ar": "ar-eg-female",
    "en": "en-us-female",
}


# Arabic Unicode range. If the text has ANY Arabic character, we treat it
# as Arabic. This handles mixed text like "الـ deploy" cleanly.
_ARABIC_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
def detect_language(text: str) -> Literal["ar", "en"]:
    """
    Detect whether text is primarily Arabic or English.

    Rules:
        - Any Arabic character present → "ar"
        - Otherwise → "en"

    Egyptian tech speech mixes English words into Arabic sentences
    constantly ("الـ PR", "الـ deploy"). If even one Arabic character is
    present, we treat the text as Arabic.
    """
    if not text or not text.strip():
        return "en"

    if _ARABIC_RE.search(text):
        return "ar"
    return "en"


# ---------------------------------------------------------------------------
# Voice + prosody resolution
# ---------------------------------------------------------------------------
def _resolve_voice(language: str, voice: str | None) -> str:
    """
    Pick the Edge TTS voice key for the given language.

    Returns a key from EDGE_VOICES (e.g. "ar-eg-female"), not the raw ID.
    """
    if voice and voice in EDGE_VOICES:
        return voice

    lang_key = language if language in DEFAULT_VOICE_BY_LANG else "en"
    return DEFAULT_VOICE_BY_LANG[lang_key]


def _resolve_prosody(voice_key: str) -> dict[str, str]:
    """
    Return the rate/pitch settings for a voice key.

    Falls back to neutral if the voice key has no tuning.
    """
    return VOICE_PROSODY.get(voice_key, {"rate": "+0%", "pitch": "+0Hz"})


# ---------------------------------------------------------------------------
# Main synthesis function
# ---------------------------------------------------------------------------
async def synthesize_async(
    text: str,
    language: Literal["auto", "ar", "en"] = "auto",
    voice: str | None = None,
) -> bytes:
    """
    Convert text to MP3 bytes using Edge TTS.

    Args:
        text:     The text to speak.
        language: "auto" (detect), "ar" (Egyptian Arabic), or "en" (English).
        voice:    Optional explicit voice key from EDGE_VOICES.

    Returns:
        Raw MP3 file bytes.

    Raises:
        RuntimeError: if synthesis fails or the text is empty.
    """
    if not text or not text.strip():
        raise RuntimeError("TTS input is empty")

    detected = detect_language(text) if language == "auto" else language
    voice_key = _resolve_voice(detected, voice)
    voice_id = EDGE_VOICES[voice_key]
    prosody = _resolve_prosody(voice_key)

    logger.info(
        "TTS: %d chars | lang=%s | voice=%s | rate=%s pitch=%s",
        len(text),
        detected,
        voice_id,
        prosody["rate"],
        prosody["pitch"],
    )

    try:
        communicator = edge_tts.Communicate(
            text=text,
            voice=voice_id,
            rate=prosody["rate"],
            pitch=prosody["pitch"],
        )
        buffer = io.BytesIO()
        async for chunk in communicator.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        audio_bytes = buffer.getvalue()
    except Exception as exc:
        logger.exception("Edge TTS failed")
        raise RuntimeError(f"TTS synthesis failed: {exc}") from exc

    if not audio_bytes:
        raise RuntimeError("TTS produced empty audio")

    logger.info("TTS: produced %d bytes of MP3", len(audio_bytes))
    return audio_bytes


def synthesize(
    text: str,
    language: Literal["auto", "ar", "en"] = "auto",
    voice: str | None = None,
) -> bytes:
    """
    Synchronous wrapper around synthesize_async.

    Useful for scripts and tests. In FastAPI, prefer the async version.

    Args:
        text:     The text to speak.
        language: "auto", "ar", or "en".
        voice:    Optional explicit voice key from EDGE_VOICES.

    Returns:
        Raw MP3 file bytes.
    """
    import asyncio

    return asyncio.run(synthesize_async(text, language=language, voice=voice))


# ---------------------------------------------------------------------------
# Introspection helpers
# ---------------------------------------------------------------------------
def list_voices() -> dict[str, str]:
    """
    Return the voice catalog for callers that want to expose voice choice.
    """
    return dict(EDGE_VOICES)


def list_prosody() -> dict[str, dict[str, str]]:
    """
    Return the prosody tuning table for introspection / debugging.
    """
    return {k: dict(v) for k, v in VOICE_PROSODY.items()}