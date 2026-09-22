"""Create the five requested offline fallback audio slots.

The repository cannot manufacture meaningful MP3 speech without an audio asset.
This helper copies user-supplied MP3s into stable names and validates them.
"""
from pathlib import Path

FALLBACK_NAMES = ["critical.mp3", "high.mp3", "medium.mp3", "low.mp3", "unknown.mp3"]


def install_fallbacks(source_dir: str | Path, target_dir: str | Path = ".spectre/voice_fallbacks") -> list[Path]:
    source = Path(source_dir)
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for name in FALLBACK_NAMES:
        src = source / name
        if src.exists() and src.stat().st_size > 0:
            dst = target / name
            dst.write_bytes(src.read_bytes())
            copied.append(dst)
    return copied
