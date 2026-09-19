"""OpenAI TTS with deterministic disk caching and five offline fallback clips."""
from __future__ import annotations

import hashlib
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import re
from pathlib import Path
from typing import Any

VOICES = {
    "devops": "onyx",
    "executive": "nova",
    "critical": "echo",
    "default": "alloy",
}

CACHE_DIR = Path(os.getenv("SPECTRE_VOICE_CACHE", ".spectre/voice_cache"))
FALLBACK_DIR = Path(__file__).resolve().parent / "fallbacks"
MAX_INPUT_CHARS = 4000


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)


def fallback_audio(level: str = "unknown") -> str:
    """Return one of the five packaged MP3 clips."""
    level = level.lower()
    path = FALLBACK_DIR / f"{level}.mp3"
    if not path.exists():
        path = FALLBACK_DIR / "unknown.mp3"
    if not path.exists():
        raise RuntimeError("No fallback voice assets are installed")
    return str(path)


def text_to_speech(text: str, voice_key: str = "default", *, output_dir: str | Path | None = None, fallback_level: str | None = None) -> str:
    text = text.strip()
    if not text:
        raise ValueError("Text is empty")
    voice = VOICES.get(voice_key, VOICES["default"])
    directory = Path(output_dir) if output_dir else CACHE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(f"{text}\n{voice}".encode("utf-8")).hexdigest()[:24]
    output_file = directory / f"{cache_key}_{_safe_name(voice)}.mp3"
    if output_file.exists():
        return str(output_file)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        if fallback_level:
            return fallback_audio(fallback_level)
        raise RuntimeError("OPENAI_API_KEY is required to generate speech")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
        kwargs: dict[str, Any] = {
            "model": model,
            "voice": voice,
            "input": text[:MAX_INPUT_CHARS],
            "response_format": "mp3",
        }
        instructions = os.getenv("OPENAI_TTS_INSTRUCTIONS")
        if instructions and model == "gpt-4o-mini-tts":
            kwargs["instructions"] = instructions
        response = client.audio.speech.create(**kwargs)
        response.stream_to_file(str(output_file))
        return str(output_file)
    except Exception:
        if fallback_level:
            return fallback_audio(fallback_level)
        raise
