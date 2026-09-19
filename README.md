# Spectre Impact

Spectre Impact turns changed files into a deterministic dependency-graph blast radius, business-impact estimate, deployment guidance, AI review, voice output, and RAG context.

## What is implemented

- **Impact engine:** resource detection → BFS blast radius → business impact → severity → deployment strategy → rollback requirement.
- **FastAPI:** `/api/analyze`, `/api/review`, `/api/chat`, `/api/voice/{pr_number}`, `/webhook/github`, `/health`.
- **Code review:** Semgrep + Bandit + Radon + AI review. Missing local tools are reported as `skipped`, not fatal.
- **AI fallback:** Groq → OpenAI → Anthropic, controlled by `SPECTRE_AI_PROVIDERS`.
- **Voice:** OpenAI TTS with SHA-256 disk caching plus five packaged fallback MP3s.
- **CLI:** `init`, `analyze`, `review`, `chat`, `watch`, `config`, `auth`, `report`, and `rag ingest/search`.
- **RAG:** ChromaDB persistent store with a JSON lexical fallback; indexes curated component/business metadata and repository source chunks.
- **Multi-user safety:** API work is per-request; chat sessions are isolated by session ID. Redis can be used for cross-worker/session persistence; local development uses a bounded TTL store.
- **Auto discovery:** existing proposed map generator remains available and never overwrites curated maps.

## Setup

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

Set at least one AI provider key if you want AI features. Deterministic analysis works without any AI key.

Run tests:

```bash
python -m pytest -q
```

Run API:

```bash
uvicorn backend.main:app --reload
```

Run CLI:

```bash
python -m cli.main init
python -m cli.main analyze --base main
python -m cli.main review change.diff
python -m cli.main rag ingest . --target-docs 500
python -m cli.main rag search "payment service rollback"
```

## Voice

`voice/tts.py` caches generated MP3s by text + voice. If OpenAI is unavailable and a fallback level is requested, one of these packaged clips is returned:

- `critical.mp3`
- `high.mp3`
- `medium.mp3`
- `low.mp3`
- `unknown.mp3`

The OpenAI TTS model defaults to `gpt-4o-mini-tts` and can be overridden with `OPENAI_TTS_MODEL`.

## RAG enrichment

The normal enrichment command indexes real repository/map data. `--target-docs` is optional and only creates clearly marked `synthetic_demo` records to make a hackathon/demo corpus reach a requested size; these are not represented as production incidents.
