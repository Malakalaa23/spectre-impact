"""Pytest configuration — adds the project root to sys.path so tests can
import modules from the project root even though they live in tests/."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))