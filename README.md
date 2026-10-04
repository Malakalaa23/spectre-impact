# Spectre Impact

**Know what breaks before you merge.**

Spectre Impact is an AI-powered GitHub change intelligence tool. It analyzes pull requests, computes blast radius from infrastructure dependencies, and explains the impact in English or Egyptian Arabic — before code reaches production.

Finalist at **DevOpsDays Cairo 2026** — top 20 of 142 teams.

---

## The problem

Modern teams use AI to write code faster. Nothing tells them what that code will *break*.

Datadog tells you what already failed. Copilot helps you write the next line. Neither tells you, at the moment of merge, which services will go down and what that will cost.

Spectre Impact fills that gap.

---

## What it does

When a developer opens a pull request, Spectre Impact:

1. **Parses** the changed files — Terraform, Python, JavaScript, and more
2. **Builds** a dependency graph from Terraform resources and module references
3. **Computes blast radius** with breadth-first search on the graph
4. **Estimates business impact** as a percentage of affected users
5. **Generates AI insights** — severity, simulation, rollback plan, validation checklist
6. **Reviews the code** for bugs, security issues, and missing tests
7. **Posts a formatted comment** on the PR with badges, tables, and checklists
8. **Answers follow-up questions** in English or Egyptian Arabic via Lya, a bilingual chat agent
9. **Speaks** the answers aloud in both languages
10. **Remembers** conversations across turns and sessions

### Core philosophy

- **Deterministic first.** BFS computes the graph. The AI explains the result.
- **AI second.** The model never guesses numbers. It narrates them.
- **Never breaks.** Four-provider fallback chain ending in a deterministic message.
- **Always grounded.** RAG prevents hallucination. If the model doesn't know, it says so.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│              Docker container (single service)       │
│                                                       │
│   ┌─────────────────────┐    ┌────────────────────┐   │
│   │  FastAPI backend    │    │  Streamlit frontend│   │
│   │  main:app           │◄───│  frontend/app.py   │   │
│   │  port 8000          │    │  port $PORT (8501) │   │
│   │  (internal only)    │    │  (public)          │   │
│   └─────────────────────┘    └────────────────────┘   │
│                                                       │
└──────────────────────────────────────────────────────┘
```

The backend and frontend run in the same container. Streamlit reaches FastAPI via `http://localhost:8000`. Users connect to Streamlit on port 8501.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11) |
| Frontend | Streamlit |
| AI agent | Custom tool-calling loop |
| Primary LLM | Groq — `openai/gpt-oss-20b` |
| Fallback LLMs | Google Gemini, OpenAI, Anthropic |
| RAG | ChromaDB (145 documents) |
| Embeddings | IBM Granite 97M multilingual (local) |
| Speech-to-text | Whisper-small Egyptian Arabic |
| Text-to-speech | Microsoft Edge TTS |
| Memory | Redis (with in-memory fallback) |
| Database | SQLite |
| Terraform parsing | `python-hcl2` |

---

## Notable engineering decisions

### Removing LangChain

The initial implementation used `langchain.agents.create_agent`. It added 74 seconds per turn. We benchmarked against raw Groq (1.4 seconds), removed LangChain entirely, and hand-rolled the tool-calling loop. Result: a 50x speedup on the same behavior.

### Two-tier response cache

Live LLM calls have variable latency. We added a two-tier cache in `rag/retriever.py`:

- **Tier 1:** normalized string match (2 ms). Handles Arabic diacritics, alef/ya/ta-marbuta variants, and whitespace normalization.
- **Tier 2:** semantic search in ChromaDB (~300 ms).

Rehearsed queries return in under a second. Unrehearsed queries fall through to the full LLM flow.

### Multi-provider fallback

The chat agent routes through `ai/multi_provider.py`, which tries:

```
Groq → Google Gemini → OpenAI → Anthropic → deterministic message
```

A 429 on one provider does not surface to the user.

### Input and output safety

`chat/safety.py` runs regex guards on both sides:

- **Input:** blocks prompt injection, secret harvesting, destructive commands
- **Output:** redacts API keys, JWTs, and hex secrets before the user sees them

---

## Running locally

### Requirements

- Python 3.11+
- Git

### Setup

```bash
git clone https://github.com/Malakalaa23/spectre-impact.git
cd spectre-impact
python -m venv venv
```

Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source venv/bin/activate
```

Then:

```bash
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the repo root:

```
GROQ_API_KEY=your_groq_key
GOOGLE_API_KEY=your_google_key
GITHUB_TOKEN=your_github_token
DATABASE_URL=sqlite:///history.db
```

Get keys:

- Groq: https://console.groq.com/keys
- Google Gemini: https://aistudio.google.com/apikey
- GitHub token: https://github.com/settings/tokens (scopes: `repo`, `pull_request`)

### Run

Terminal 1 — backend:

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

Terminal 2 — frontend:

```bash
streamlit run frontend/app.py --server.port 8501
```

Open `http://localhost:8501`.

---

## Testing

```bash
pytest test_spectre.py -v
```

Tests cover the BFS engine, chat agent, RAG retrieval, safety guards, TTS, STT, rollback executor, and API endpoints.

---

## Known limitations

We'd rather tell you than have you find out.

- **Not validated at scale.** The dependency graph is hand-crafted for a demo repository. It has not been tested on messy real-world infrastructure.
- **Rollback executor runs in demo mode.** It validates commands, logs them, and simulates execution. It does not run against a real cluster yet.
- **Business map is manual.** Mapping services to revenue requires a short onboarding workshop. Automating this is on the roadmap.
- **No paying customers yet.** We validated the technology and the problem with 12 engineer interviews. We have not validated the market with a sale.
- **Egyptian TTS is dialect-aware, not native.** We're evaluating NAMAA and Chatterbox Masri for Phase 2.

---

## Roadmap

**Phase 1 (Q1 2027)**

- PyPI publication
- GitHub App listing
- Feedback widget in the UI

**Phase 2 (Q2–Q3 2027)**

- Kubernetes parser (not just Terraform)
- Server-sent events for streaming responses
- Native Egyptian Arabic TTS

**Phase 3 (Q4 2027)**

- Multi-dialect Arabic (Gulf, Levantine, Moroccan)
- GitLab and Bitbucket integrations
- Predictive failure detection

---

## Team

Built over three months by five engineers:

- **Malak Alaa** — AI Systems Engineer (chat agent, RAG, multi-provider AI, deployment)
- **Ahmed Ashraf** — Backend Engineer (rollback executor, CLI, deployment)
- **Abu Bakr Khaled** — Backend Engineer (TTS, code review, RAG data)
- **Merna Antar** — Frontend Developer (chat UI, STT, rollback UI)
- **Habiba Ahmed** — UI/UX Designer (voice UI, design polish)

---

## Acknowledgements

Built for **DevOpsDays Cairo 2026**, organized by ITIDA and Creativa Innovation Hub. Finalist among 20 teams from 142 initial entries.

Thanks to the judges for their time and feedback: Yvo van Doorn, Hossam Gaber, Ahmed Saed, Ron D.

---

## License

MIT License — see [LICENSE](LICENSE) for details.