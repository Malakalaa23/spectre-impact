"""
app.py — Hugging Face Spaces entry point.

HF Spaces expects a Python file at the root that imports the FastAPI app.
This file's ONLY job is to import `app` from `main.py` so HF can find it.

For the Streamlit dashboard, see dashboard/app.py instead.
"""

import os
import sys
from pathlib import Path

# Ensure project root is on the path
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import the FastAPI app from main.py
from main import app  # noqa: E402


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)