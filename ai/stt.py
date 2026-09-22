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
from pathlib import Path
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

# Whisper models expect 16 kHz mono audio. The frontend sends whatever
# the browser records (usually 48 kHz stereo webm). We normalize here.


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
# Audio normalization
# ---------------------------------------------------------------------------
def _normalize_audio_to_wav(input_bytes: bytes, input_suffix: str) -> str:
    """
    Convert arbitrary audio bytes to 16 kHz mono WAV on disk.

    Whisper expects this format. Browser recordings are typically webm
    or opus. pydub + ffmpeg handles the conversion.

    Returns the path to the WAV file. Caller is responsible for cleanup.
    """
    from pydub import AudioSegment

    # Write the raw bytes to a temp file first
    with tempfile.NamedTemporaryFile(suffix=input_suffix, delete=False) as f:
        f.write(input_bytes)
        input_path = f.name

    try:
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_frame_rate(16000).set_channels(1)

        output_path = input_path + ".wav"
        audio.export(output_path, format="wav")
        return output_path
    finally:
        # The original temp file is no longer needed
        try:
            os.unlink(input_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------
def _transcribe_sync(audio_bytes: bytes, language: Optional[str] = None) -> str:
    """
    Synchronous transcription. Callers wrap this in asyncio.to_thread.
    """
    model = _get_model()
    if model is None:
        raise RuntimeError("STT model unavailable")

    # Detect the input format from common magic bytes
    suffix = ".webm"
    if audio_bytes[:4] == b"RIFF":
        suffix = ".wav"
    elif audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb":
        suffix = ".mp3"
    elif audio_bytes[:4] == b"OggS":
        suffix = ".ogg"
    elif audio_bytes[:4] == b"\x1a\x45\xdf\xa3":
        suffix = ".webm"

    wav_path = _normalize_audio_to_wav(audio_bytes, suffix)

    try:
        # language=None lets Whisper auto-detect. For mixed Arabic/English
        # it usually picks the dominant language, which is fine because
        # the model was fine-tuned on code-switching.
        segments, info = model.transcribe(
            wav_path,
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
            os.unlink(wav_path)
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
        audio_bytes: Raw audio file contents (webm, wav, mp3, ogg).
        language: Optional ISO code ("ar", "en"). None = auto-detect.

    Returns:
        Transcribed text. Empty string if no speech detected.

    Raises:
        RuntimeError: if the model is unavailable or transcription fails.
    """
    if not audio_bytes:
        raise ValueError("Empty audio")

    return await asyncio.to_thread(_transcribe_sync, audio_bytes, language)