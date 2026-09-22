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
    bindings. No system ffmpeg is required. We pass the raw bytes
    straight to transcribe() and PyAV handles webm, mp3, ogg, wav,
    and everything else the browser records.

Model:
    Mano200600/faster-whisper-small-egyptian-ar
    Fine-tuned on Egyptian Arabic speech. Handles English code-switching
    (common when developers say "payment service" in an Arabic sentence).

Public API:
    transcribe_async(audio_bytes, language) -> str
        Async wrapper. Returns the transcribed text.
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
COMPUTE_TYPE = os.getenv("SPECTRE_STT_COMPUTE", "int8")  # int8 is best for CPU


# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------
_model = None
_model_failed = False


def _get_model():
    """
    Load the faster-whisper model once and cache it.

    Returns None if loading fails. Callers should return a 503
    in that case rather than crash.
    """
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
# Transcription
# ---------------------------------------------------------------------------
def _detect_suffix(audio_bytes: bytes) -> str:
    """
    Guess the audio container from the file's magic bytes.

    faster-whisper (via PyAV) will decode the format on its own, but
    giving it a file with the right extension avoids ambiguity when the
    bytes could be misdetected.

    Browsers send webm/opus by default for MediaRecorder, wav for
    st.audio_input on some builds, mp3/m4a for uploads.
    """
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
    """
    Synchronous transcription. Callers wrap this in asyncio.to_thread.
    """
    model = _get_model()
    if model is None:
        raise RuntimeError("STT model unavailable")

    suffix = _detect_suffix(audio_bytes)

    # faster-whisper accepts either a path or a file-like object. We
    # use a NamedTemporaryFile so PyAV can seek if it needs to.
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name

    try:
        # language=None lets Whisper auto-detect. For mixed Arabic/English
        # it usually picks the dominant language, which is fine because
        # the model was fine-tuned on code-switching.
        segments, info = model.transcribe(
            temp_path,
            language=language,
            beam_size=5,
            vad_filter=True,            # skip silence — faster and cleaner
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def transcribe_async(
    audio_bytes: bytes,
    language: Optional[str] = None,
) -> str:
    """
    Transcribe audio bytes to text.

    Args:
        audio_bytes: Raw audio file contents (webm, wav, mp3, ogg, m4a).
        language: Optional ISO code ("ar", "en"). None = auto-detect.

    Returns:
        Transcribed text. Empty string if no speech detected.

    Raises:
        RuntimeError: if the model is unavailable or transcription fails.
    """
    if not audio_bytes:
        raise ValueError("Empty audio")

    return await asyncio.to_thread(_transcribe_sync, audio_bytes, language)