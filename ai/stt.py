"""
stt.py — Speech-to-text for Lya using faster-whisper.

Transcribes Arabic (Egyptian dialect) and English audio. Uses a
fine-tuned Egyptian Arabic Whisper model converted to CTranslate2
format for fast CPU inference.

Why faster-whisper over openai-whisper:
    - 4x faster on CPU via CTranslate2
    - ~2x less RAM
    - Same accuracy
    - Runs offline after the first model download

Audio decoding:
    faster-whisper uses PyAV internally, which ships its own libav
    bindings. No system ffmpeg is required.

Public API:
    transcribe_async(audio_bytes, language) -> str
        Async wrapper. Returns the transcribed text.

    warmup() -> None
        Runs short clips through the model to warm every code path
        the first real inference would otherwise pay for.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL_ID = os.getenv(
    "SPECTRE_STT_MODEL",
    "Mano200600/faster-whisper-small-egyptian-ar",
)
DEVICE = os.getenv("SPECTRE_STT_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("SPECTRE_STT_COMPUTE", "int8")

# Beam size for real transcriptions. 1 is ~3x faster than 5 with
# negligible quality loss on short conversational clips.
BEAM_SIZE = int(os.getenv("SPECTRE_STT_BEAM_SIZE", "1"))


# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------
_model = None
_model_failed = False


def _get_model():
    """Load the faster-whisper model once and cache it."""
    global _model, _model_failed

    if _model_failed:
        return None
    if _model is not None:
        return _model

    try:
        from faster_whisper import WhisperModel

        logger.info("Loading STT model: %s (device=%s, compute=%s)",
                    MODEL_ID, DEVICE, COMPUTE_TYPE)

        _model = WhisperModel(
            MODEL_ID,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
        )
        logger.info("STT model loaded")
        return _model

    except ImportError as exc:
        logger.warning("faster-whisper not installed: %s", exc)
        _model_failed = True
        return None
    except Exception as exc:
        logger.warning("STT model load failed: %s", exc)
        _model_failed = True
        return None


# ---------------------------------------------------------------------------
# Warmup
# ---------------------------------------------------------------------------
def _warmup_sync() -> None:
    """
    Run short clips through the model to warm every code path the first
    real inference would otherwise pay for:

        - Silero VAD model load (triggered by vad_filter=True)
        - CTranslate2 JIT compilation of encoder + decoder kernels
        - Internal KV cache and positional embedding caches

    A silent input with vad_filter=True is not enough — the VAD would
    reject it and the encoder would never run, so the kernel compilation
    never happens. We use two passes:

        Pass 1: 600 Hz tone, vad_filter=True.  VAD loads and detects
                the tone as speech, so the full pipeline runs.
        Pass 2: same tone, vad_filter=False.  Belt-and-braces for the
                case where VAD decides the tone is noise.

    On a cold container this saves 60-90 seconds on the first user call.
    """
    model = _get_model()
    if model is None:
        return

    try:
        import numpy as np

        # 1 second of a low-amplitude 600 Hz tone at 16 kHz mono. Loud
        # enough that Silero VAD classifies it as speech-like, quiet
        # enough that if it somehow produced text, it would be garbage.
        sample_rate = 16000
        t = np.linspace(0, 1.0, sample_rate, dtype=np.float32)
        tone = (0.05 * np.sin(2 * np.pi * 600 * t)).astype(np.float32)

        for label, use_vad in (("with VAD", True), ("without VAD", False)):
            segments, _ = model.transcribe(
                tone,
                language="en",
                beam_size=1,
                vad_filter=use_vad,
                vad_parameters={"min_silence_duration_ms": 100},
                without_timestamps=True,
            )
            # Consume the generator so inference actually executes.
            for _ in segments:
                pass
            logger.info("STT warmup pass complete (%s)", label)

        logger.info("STT warmup complete")
    except Exception as exc:
        logger.warning("STT warmup failed: %s", exc)


async def warmup() -> None:
    """Async wrapper for _warmup_sync(). Called from FastAPI startup."""
    await asyncio.to_thread(_warmup_sync)


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------
def _detect_suffix(audio_bytes: bytes) -> str:
    """Guess the audio container from magic bytes."""
    if audio_bytes[:4] == b"RIFF":
        return ".wav"
    if audio_bytes[:4] == b"OggS":
        return ".ogg"
    if audio_bytes[:4] == b"\x1a\x45\xdf\xa3":
        return ".webm"
    if audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb":
        return ".mp3"
    if audio_bytes[4:8] == b"ftyp":
        return ".m4a"
    return ".webm"


def _transcribe_sync(audio_bytes: bytes, language: Optional[str] = None) -> str:
    """Synchronous transcription. Callers wrap this in asyncio.to_thread."""
    model = _get_model()
    if model is None:
        raise RuntimeError("STT model unavailable")

    suffix = _detect_suffix(audio_bytes)

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name

    try:
        segments, info = model.transcribe(
            temp_path,
            language=language,
            beam_size=BEAM_SIZE,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )

        text = " ".join(seg.text.strip() for seg in segments).strip()
        logger.info("Transcribed %d bytes -> %d chars (lang=%s, prob=%.2f)",
                    len(audio_bytes), len(text), info.language, info.language_probability)
        return text

    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


async def transcribe_async(
    audio_bytes: bytes,
    language: Optional[str] = None,
) -> str:
    """Transcribe audio bytes to text."""
    if not audio_bytes:
        raise ValueError("Empty audio")

    return await asyncio.to_thread(_transcribe_sync, audio_bytes, language)