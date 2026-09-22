"""Write the five HF Space deployment files. Run once from repo root."""
from pathlib import Path

ROOT = Path(__file__).parent

FILES = {
    "Dockerfile": '''FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    git \\
    curl \\
    supervisor \\
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \\
    PATH=/home/user/.local/bin:$PATH \\
    PYTHONUNBUFFERED=1 \\
    PYTHONDONTWRITEBYTECODE=1 \\
    HF_HOME=/home/user/.cache/huggingface \\
    TRANSFORMERS_CACHE=/home/user/.cache/huggingface \\
    SENTENCE_TRANSFORMERS_HOME=/home/user/.cache/huggingface

WORKDIR $HOME/app

COPY --chown=user requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \\
    pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \\
    CMD curl -f http://localhost:7860/_stcore/health || exit 1

CMD ["supervisord", "-c", "/home/user/app/supervisord.conf"]
''',

    "supervisord.conf": '''[supervisord]
nodaemon=true
user=user
logfile=/tmp/supervisord.log
pidfile=/tmp/supervisord.pid

[program:api]
command=uvicorn main:app --host 127.0.0.1 --port 8000
directory=/home/user/app
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
environment=PYTHONUNBUFFERED="1"

[program:ui]
command=streamlit run frontend/app.py --server.port 7860 --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false
directory=/home/user/app
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
environment=PYTHONUNBUFFERED="1",SPECTRE_BACKEND_URL="http://127.0.0.1:8000"
''',

    "README.md": '''---
title: Spectre Impact
emoji: 🚀
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: AI-powered GitHub change intelligence, bilingual EN/AR
---

# Spectre Impact

**Know what breaks before you deploy.**

Copilot helps you write code faster. We help you ship it safer — in English
and Egyptian Arabic.

## What it does

When a Pull Request is opened on GitHub, Spectre Impact:

1. Computes the blast radius via BFS on a dependency graph
2. Scores business impact as a percentage of affected users
3. Generates AI insights — severity, simulation, rollback plan, validation
4. Reviews the code — bugs, security issues, missing tests
5. Posts a formatted PR comment with badges, tables, and evidence chains
6. Answers follow-up questions via Lya, a bilingual chat agent
7. Speaks answers in English or Egyptian Arabic
8. Remembers conversations across sessions
9. Learns from user feedback

## Architecture

- **Backend:** FastAPI (Python 3.11)
- **Frontend:** Streamlit
- **AI Agent:** LangChain + LangGraph
- **LLMs:** Groq (primary) then OpenAI then Anthropic then deterministic fallback
- **RAG:** ChromaDB + IBM granite-embedding-97m-multilingual-r2 (local embeddings)
- **STT:** faster-whisper
- **TTS:** Edge TTS (English + Egyptian Arabic)
- **Memory:** Redis with in-memory fallback
- **Storage:** SQLite (WAL mode)

## Endpoints

- POST /webhook — GitHub webhook receiver
- POST /api/chat — Lya chat
- POST /api/tts — text-to-speech
- POST /api/stt — speech-to-text
- POST /api/feedback — feedback collection
- GET /api/analyses — list recent PR analyses
- GET /api/live-feed — synthetic demo events
- GET /ping — health check
''',

    ".dockerignore": '''venv/
.venv/
__pycache__/
*.pyc
*.pyo
*.pyd
.pytest_cache/
.mypy_cache/
.ruff_cache/
.git/
.gitignore
.github/

.env
.env.docker
.env.local

test_*.py
diagnose_*.py
preflight.py
fix_encoding.py
make_deploy_files.py
check_*.py
audit_*.py
list_*.py
dump_*.py
rebuild_*.py
multi_level_summary.py
analyze_frontend.py
project_check.py
integration.py

test_audio.wav
test_speech.ogg

.DS_Store
Thumbs.db

*.md
!README.md

_archive_*/

.vscode/
.idea/

terraform/

rag_db/.cache/
''',

    ".env.example": '''# Spectre Impact — environment variables
# Copy to .env locally. On HF Space, set these as Repository Secrets.

# --- Required ---
SESSION_SECRET=change-me-to-a-long-random-string
GITHUB_TOKEN=ghp_your_token_here
GROQ_API_KEY=gsk_your_groq_key_here

# --- Optional fallback providers ---
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# --- Public URL (used in PR comment signature + QR) ---
SPECTRE_PUBLIC_URL=https://your-space-name.hf.space

# --- Ports ---
PORT=7860

# --- Redis (optional; falls back to in-memory) ---
REDIS_URL=

# --- STT model ---
SPECTRE_STT_MODEL=Mano200600/faster-whisper-small-egyptian-ar
SPECTRE_STT_DEVICE=cpu
SPECTRE_STT_COMPUTE=int8
''',
}

for name, content in FILES.items():
    path = ROOT / name
    path.write_text(content, encoding="utf-8")
    print(f"  wrote {name:<24} {len(content.encode('utf-8'))} bytes")

print()
print("Done. 5 files written.")