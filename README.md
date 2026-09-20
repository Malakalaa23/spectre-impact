# Spectre Impact — Developer + Business Dashboard

This version merges the original dashboard with the requested developer real-time workflow and a separate business view.

## What is included

- Frontend pages: AI Chat, Code Review, Voice Analysis, Rollback Center, and QR Landing.
- Reusable API client, active custom CSS, chat session memory, TTS controls, microphone/STT hook, review findings/diff viewer, rollback states, and QR generation.

- Developer dashboard with real-time code-change activity.
- GitHub webhook receiver (`realtime_server.py`).
- Automatic dashboard refresh every 2 seconds when `streamlit-autorefresh` is installed.
- Developer-only live activity and team communication.
- Business-only plain-language dashboard with no technical code details.
- Severity/repository/developer filters.
- PR deep dive with engineer/executive summaries, impact simulation, rollback plan and validation checklist.
- Deterministic local BFS blast-radius fallback.
- Safe local AI-style fallback when the real AI service is unavailable.
- GitHub comment bridge with a safe fallback when no token/API is configured.
- Remote API support through `SPECTRE_DATA_API_URL`; local data remains available if the API fails.
- Dockerfile and Docker Compose for dashboard + webhook server.
- Error handling that keeps the UI alive when external services fail.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`.

## Run the real-time webhook server

```bash
uvicorn realtime_server:app --host 0.0.0.0 --port 8000
```

Health: `GET /health`
Events: `GET /events`
PRs: `GET /prs`
Webhook: `POST /webhook/github`
GitHub comment bridge: `POST /github/comment`

Configure a GitHub Pull Request webhook to call `/webhook/github`. For a public local demo, expose port 8000 with your approved tunnel (for example ngrok).

## Docker

```bash
docker compose up --build
```

Dashboard: `http://localhost:8501`
Realtime API: `http://localhost:8000/health`

## Real-time flow

```text
Developer
   ↓
GitHub Pull Request / Push
   ↓
Webhook
   ↓
FastAPI realtime_server.py
   ↓
BFS blast-radius fallback + AI analysis fallback
   ↓
runtime_data/events.json
   ↓
Developer Dashboard refresh
   ↓
Live warning + team communication
```

The dashboard does not depend on the webhook server to render. If the API goes down, it keeps showing the last known local data and changes the status badge to CACHED instead of crashing.
