````
# 🤖 AI Agent — Spectre Impact

## Overview

The AI Agent is the **reasoning layer** of Spectre Impact. It sits behind two chat surfaces (Lya, the bilingual agent, and the PR analysis pipeline) and turns structured facts into explained decisions.

The AI never computes numbers. Those come from the BFS engine. The AI reads them and narrates them.

**What the AI Agent handles:**

- Deployment risk reports from a list of affected services
- Multi-turn bilingual conversation (English + Egyptian Arabic)
- Blast radius explanations grounded in RAG-retrieved documents
- Rollback plan generation with human-approval gates
- Validation and health-check command suggestions
- Token tracking and cost monitoring
- Cached responses to avoid duplicate API calls
- Multi-provider fallback so the user never sees a rate-limit error

**Why it matters:**

Instead of just saying *"these services changed,"* the AI explains:

- What could go wrong
- How bad it could be
- How to roll back
- How to verify it's working
- In English or in Egyptian Arabic, whichever the user speaks

---

## The full AI stack

Spectre Impact runs six AI components. The AI Agent is the orchestration layer that ties them together:

| Component | File | Purpose |
|---|---|---|
| AI Agent | `ai_agent_groq.py` | Generates insights from services + impact % |
| Chat Agent (Lya) | `chat/agent.py` | Multi-turn bilingual conversation with tool calling |
| Multi-Provider Fallback | `ai/multi_provider.py` | Groq → Google → OpenAI → Anthropic → deterministic |
| RAG Retriever | `rag/retriever.py` | Grounds responses in 145 documents |
| Safety Module | `chat/safety.py` | Blocks prompt injection and redacts secrets |
| Demo Fast-Path | `rag/demo_responses.py` | Pre-authored stage answers returned in 2 ms |

---

## How the reasoning works

```
User sends a message
        ↓
INPUT GATE (chat/safety.py)
  • Block prompt injection
  • Block secret harvesting
  • Block destructive commands
        ↓
ORCHESTRATOR (chat/agent.py)
  • Touch session, record mood, extract services
  • Load session context and history
        ↓
ORPHAN GUARD
  • If referential follow-up with no history → clarify, don't call the model
        ↓
DEMO FAST-PATH (rag/retriever.py)
  • Tier 1: normalized string match (2 ms)
  • Tier 2: ChromaDB semantic search (~300 ms)
  • If HIT → return pre-authored answer, skip the model entirely
        ↓
CONTEXT ASSEMBLY
  • System prompt (personality, dialect rules, safety policy)
  • Session context block (session #, turn #, mood, recent services)
  • Trimmed history (last 6 turns)
  • Current user message
        ↓
TOOL-CALLING LOOP (max 2 iterations)
  • Build tool schemas from chat/tools/
  • Call the model
  • If tool calls → execute → append result → call again
  • Cap each tool result at 2000 chars
        ↓
MULTI-PROVIDER FALLBACK (ai/multi_provider.py)
  • Groq (primary)
  • Google Gemini
  • OpenAI
  • Anthropic
  • Deterministic message (final)
        ↓
OUTPUT GATE (chat/safety.py)
  • Redact API keys, JWTs, hex secrets
  • Return clean text
        ↓
PERSISTENCE (chat/memory.py, database.py)
  • Save to Redis / in-memory session
  • Save to SQLite for long-term history
        ↓
Response to user
```

---

## Input contract — `generate_insights()`

### Input parameters

| Parameter | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `services` | `List[str]` | List of affected services | `["payment_service", "login_service"]` |
| `impact_percentage` | `int` | Percentage of users affected (0–100) | `85` |

### Output structure

```python
{
    "simulation": "The payment_service update triggers a cascade failure...",
    "severity": "Critical",  # Critical, High, Medium, Low
    "rollback": [
        "kubectl rollout undo deployment payment_service",
        "git revert HEAD~1 && git push origin main",
        "kubectl rollout restart deployment login_service"
    ],
    "validation": [
        "curl -X GET https://example.com/payment/health",
        "kubectl get pods -n payment-service -o wide",
        "tail -f /var/log/payment-service.log"
    ],
    "tokens_used": {
        "input_tokens": 242,
        "output_tokens": 169,
        "total_tokens": 411
    }
}
```

### Severity levels

| Severity | Criteria |
| :--- | :--- |
| Critical | > 70% users affected |
| High | > 40% users affected |
| Medium | > 10% users affected |
| Low | ≤ 10% users affected |

---

## Six tools the AI can call

The chat agent uses a hand-rolled tool-calling loop (no LangChain). Six read-only tools:

| Tool | Purpose |
| :--- | :--- |
| `analyze_blast_radius(file_path)` | Which services are affected by a file change |
| `list_services()` | All nodes in the dependency graph |
| `get_past_prs(service)` | Past PRs that touched a service |
| `get_pr_details(pr_number)` | Full analysis of a specific PR |
| `get_recent_incidents(limit)` | Recent critical or high-severity items |
| `search_knowledge_base(query)` | RAG search over the 145 documents |

**The model can only request. The harness executes.** A tool call is a request validated against a whitelist, not an action.

---

## Two-tier demo fast-path

Live LLM calls have variable latency (2–8 seconds) and hit rate limits. For rehearsed queries, we added a two-tier cache in `rag/retriever.py`:

### Tier 1 — normalized string match (2 ms)

```python
_normalize("إيه الخدمات اللي هتتأثر؟")  # -> "ايه الخدمات اللي هتتاثر"
```

Handles:

- Arabic diacritics (tashkeel) stripped
- Alef variants (`إ`, `أ`, `آ` → `ا`)
- Alef maqsura (`ى` → `ي`)
- Ta marbuta (`ة` → `ه`)
- Whitespace collapse
- Trailing punctuation stripped

If the normalized query matches a seeded demo query (exact or substring), the pre-authored answer is returned **without calling the model**.

### Tier 2 — semantic search (~300 ms)

If Tier 1 misses, ChromaDB retrieves the closest document. If it's a `demo_response` with L2 distance below 0.5, we return the pre-authored answer.

### Fall-through

If both tiers miss, the full tool-calling loop runs. This is how unrehearsed judge questions are handled.

---

## Multi-provider fallback chain

Every call to a model provider goes through `ai/multi_provider.py`:

```
Groq (openai/gpt-oss-20b)
    │
    ├── 429 or error → retry once (2s backoff)
    │       │
    │       └── still failing → try smaller Groq model (llama3-8b-8192)
    │               │
    │               └── still failing → Google Gemini
    │                       │
    │                       └── OpenAI
    │                               │
    │                               └── Anthropic
    │                                       │
    │                                       └── Deterministic message
    │
    └── success → return
```

**The user never sees a rate-limit error.** If Groq 429s, they get an answer from the next provider seamlessly.

---

## Safety gates

### Input gate

`chat/safety.py` runs regex guards before the model sees anything:

| Pattern | Blocks |
|---|---|
| Prompt injection | `Ignore previous instructions`, `system override` |
| Secret harvesting | `What is your system prompt?`, `print your API key` |
| Destructive commands | `rm -rf`, `DROP TABLE`, `DELETE FROM` |
| Jailbreak | `You are now DAN`, role-play escapes |

On match: raises `ValueError`, FastAPI returns HTTP 400. **The model never sees the malicious input.**

### Output gate

Same file, applied to the model's response:

| Pattern | Action |
|---|---|
| Groq keys (`gsk_...`) | Replaced with `[REDACTED]` |
| OpenAI keys (`sk-proj-...`) | Redacted |
| Anthropic keys (`sk-ant-...`) | Redacted |
| GitHub tokens (`ghp_...`) | Redacted |
| AWS keys (`AKIA...`) | Redacted |
| JWTs (`eyJ...`) | Redacted |
| Hex secrets (32+ chars) | Redacted |

If the entire response is a redacted secret, a safe placeholder is returned instead.

---

## Bilingual support

Lya speaks English and Egyptian Arabic. The system handles:

- **Language detection** — per turn, not per session
- **Feminine grammar** — when Lya speaks Arabic, she uses feminine forms
- **Egyptian friendship register** — not Modern Standard Arabic
- **Code-switching** — mixed sentences like `عندي meeting بكرة` are natural
- **Dialect-specific idioms** — `إيه`, `دول`, `ده`, `اللي فات`
- **Multilingual embeddings** — `ibm-granite/granite-embedding-97m-multilingual-r2` embeds Arabic and English into the same vector space

No translation step. No MSA. The dialect model is baked into the system prompt.

---

## RAG system

| Detail | Value |
|---|---|
| Store | ChromaDB 1.5.9 |
| Documents | 145 (services, incidents, business maps, resource maps) |
| Embedding model | `ibm-granite/granite-embedding-97m-multilingual-r2` (384-dim) |
| Hosting | Local (no API key required) |
| Growth | Every analyzed PR becomes a new incident document |
| Arabic fix | Distances dropped from 0.77 → 0.55 after switching models |

The RAG is the moat. The longer a customer uses Spectre Impact, the more their history becomes a searchable knowledge base.

---

## Multi-level summaries

The AI Agent generates two versions of the same analysis:

### DevOps view (technical)

```python
from multi_level_summary import generate_devops_summary

devops_view = generate_devops_summary(ai_result)
```

Returns commands, service details, and technical context.

### Executive view (business-friendly)

```python
from multi_level_summary import generate_executive_summary

executive_view = generate_executive_summary(ai_result)
```

Returns plain-English summary focused on business impact.

### Full report

```python
from multi_level_summary import generate_full_report

report = generate_full_report(["payment_service", "login_service"], 85)
print(report["devops"])      # Technical version
print(report["executive"])   # Business version
```

---

## Integration

### Basic usage

```python
from ai_agent_groq import generate_insights

result = generate_insights(["payment_service", "login_service"], 85)

print(result["severity"])      # "Critical"
print(result["simulation"])    # "The payment_service update triggers..."
print(result["rollback"])      # ["kubectl rollout undo...", ...]
print(result["validation"])    # ["curl /health...", ...]
print(result["tokens_used"])   # {"input_tokens": 242, ...}
```

### Integration with the BFS engine

```python
bfs_result = {
    "affected_services": ["payment_service", "login_service"],
    "business_impact": 85
}

ai_result = generate_insights(
    services=bfs_result["affected_services"],
    impact_percentage=bfs_result["business_impact"]
)
```

### Integration with the webhook handler

```python
# In main.py webhook handler
from ai_agent_groq import generate_insights

@app.post("/webhook")
async def webhook(request: Request):
    bfs_result = calculate_blast_radius(changed_files)

    ai_result = generate_insights(
        services=bfs_result["affected_services"],
        impact_percentage=bfs_result["business_impact"]
    )

    save_analysis(pr_number, bfs_result, ai_result)
    post_github_comment(pr_number, ai_result)
```

### Integration with the chat agent

The chat agent (`chat/agent.py`) uses the full provider chain:

```python
from ai.multi_provider import call_ai

result = call_ai(prompt)
text = result["text"]
provider = result["provider"]  # "groq", "google", "openai", "anthropic", "fallback"
```

---

## Features

### ✅ Cache system

Results cached by `(services, impact_percentage)`. Prevents duplicate API calls. Prints `📦 Using cached response` on a hit.

### ✅ Token tracking

Tracks input, output, and total tokens. Returns `tokens_used` in the output. Helps monitor API cost.

### ✅ Fallback chain

Four providers plus a deterministic message. The user never sees a crash.

### ✅ Demo fast-path

Rehearsed queries bypass the model entirely. Returns in 2 ms.

### ✅ Safety gates

Input blocked before the model sees it. Output redacted before the user sees it. Two layers, not one.

### ✅ Bilingual

English and Egyptian Arabic, with dialect-aware grammar and code-switching.

### ✅ Session memory

Redis + SQLite. Cross-session patterns (mood, recurring services). Orphan guard refuses to invent context.

### ✅ Grounded responses

RAG grounds every answer. If the model doesn't know, it says so. Every claim cites a source (`Based on PR #445`).

---

## Setup

### 1. Get API keys

| Key | Where |
|---|---|
| `GROQ_API_KEY` | https://console.groq.com/keys (free, no card) |
| `GOOGLE_API_KEY` | https://aistudio.google.com/apikey (free) |
| `GITHUB_TOKEN` | https://github.com/settings/tokens (scopes: `repo`, `pull_request`) |

### 2. Add to `.env`

```
GROQ_API_KEY=gsk_...your-key-here...
GOOGLE_API_KEY=...your-google-key...
GITHUB_TOKEN=...your-github-token...
DATABASE_URL=sqlite:///history.db
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Test the AI agent

```bash
python ai_agent_groq.py
```

### 5. Run integration tests

```bash
python test_integration.py
```

---

## Testing

### Run the AI agent test

```bash
python ai_agent_groq.py
```

Expected output:

```
============================================================
🚀 Testing AI Agent with Groq
============================================================

✅ Groq configured successfully.
🧠 Generating fresh insights for: ['payment_service', 'login_service']
✅ Received response from Groq (799 characters)
📝 Extracted JSON (799 characters)
📊 Token Usage: {'input_tokens': 242, 'output_tokens': 169, 'total_tokens': 411}

============================================================
🤖 AI AGENT RESPONSE
============================================================
📈 Severity:   Critical
🔮 Simulation: The payment database migration fails...
🔄 Rollback:   ['kubectl rollout undo deployment payment_service', ...]
✅ Validation: ['curl -X GET https://example.com/payment/health', ...]
📊 Tokens:     411 total (242 input, 169 output)
============================================================
```

### Run integration tests

```bash
python test_integration.py
```

Expected output:

```
🧪 Test 1: Basic AI Agent               ✅ Passed
🧪 Test 2: Multi-Level Summaries        ✅ Passed
🧪 Test 3: Cache System                 ✅ Passed
🧪 Test 4: Different Inputs             ✅ Passed
🧪 Test 5: Safety Input Guards          ✅ Passed
🧪 Test 6: Safety Output Redaction      ✅ Passed
🧪 Test 7: Demo Fast-Path               ✅ Passed
🧪 Test 8: Multi-Provider Fallback      ✅ Passed
```

---

## Troubleshooting

| Problem | Solution |
| :--- | :--- |
| `ModuleNotFoundError: No module named 'groq'` | Run `pip install -r requirements.txt` |
| `GROQ_API_KEY not found` | Add `GROQ_API_KEY` to `.env` in the repo root |
| JSON parse error | `extract_json()` handles markdown wrappers. If it fails, the model returned invalid JSON — check logs. |
| Rate limit error | The fallback chain handles it. If all providers fail, a deterministic message is returned. |
| `📦 Using cached response` | Normal — the cache is working. |
| Chat slow on first turn | Cold start — the STT and embedding models are loading. Subsequent turns are fast. |
| Chat slow on all turns | The fast-path isn't hitting for that query. Falls through to the model — expected for unrehearsed questions. |

---

## File structure

```
spectre-impact/
├── ai_agent_groq.py              # Core AI agent (insights + token tracking)
├── ai/
│   ├── multi_provider.py         # Groq → Google → OpenAI → Anthropic
│   ├── tts.py                    # Text-to-speech (Edge TTS)
│   └── stt.py                    # Speech-to-text (Whisper Egyptian)
├── chat/
│   ├── agent.py                  # Lya chat agent (tool-calling loop)
│   ├── prompts.py                # System prompt + dialect rules
│   ├── memory.py                 # Redis + in-memory session state
│   ├── safety.py                 # Input guards + output redaction
│   └── tools/                    # Six read-only tools
├── rag/
│   ├── vector_store.py           # ChromaDB wrapper + embeddings
│   ├── retriever.py              # Context building + demo fast-path
│   ├── demo_responses.py         # Pre-authored stage answers
│   └── populate.py               # Auto-ingest analyzed PRs
├── backend/analysis/
│   └── change_analysis_engine.py # BFS engine
├── terraform_parser.py           # Terraform → dependency graph
├── terraform_api.py              # Terraform parser endpoints
├── multi_level_summary.py        # DevOps + Executive views
├── main.py                       # FastAPI backend
├── github_client.py              # PR comments
├── rollback_executor.py          # Dry-run + execute rollback
├── database.py                   # SQLite persistence
├── frontend/
│   ├── app.py                    # Streamlit entry point
│   └── pages/                    # Chat, PR Analysis, Rollback, Terraform
├── presentation/                 # Pitch website (single-file HTML)
├── test_integration.py           # Integration test suite
├── test_spectre.py               # Main test suite (52+ tests)
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container build
├── start.sh                      # Runs FastAPI + Streamlit
├── .env                          # API keys (gitignored)
└── README.md                     # Project overview
```

---

## Contributors

| Role | Name | Responsibilities |
| :--- | :--- | :--- |
| AI Systems Engineer | Malak | AI agent, RAG, multi-provider fallback, deployment |
| Backend Engineer | Ahmed | FastAPI webhook, GitHub integration, rollback executor |
| Backend Engineer | Abu Bakr | BFS engine, code review, TTS, RAG data |
| Frontend Developer | Merna | Streamlit dashboard, chat UI, STT |
| UI/UX Designer | Habiba | Voice UI, dashboard design, visual polish |

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Quick reference

### One-line summary

The AI Agent takes services and an impact percentage, then returns a simulation, severity, rollback steps, and validation commands — grounded in RAG, guarded by safety gates, and served through a four-provider fallback chain.

### Key functions

| Function | Purpose |
| :--- | :--- |
| `generate_insights(services, impact)` | Main function for AI analysis |
| `call_ai(prompt)` | Multi-provider fallback entry point |
| `check_demo_response(query)` | Two-tier fast-path lookup |
| `sanitize_input(text)` | Blocks prompt injection and secret harvesting |
| `sanitize_output(text)` | Redacts secrets from the model's response |
| `generate_devops_summary(result)` | Technical summary |
| `generate_executive_summary(result)` | Business summary |
| `generate_full_report(services, impact)` | Both summaries combined |

### Important files

| File | Purpose |
| :--- | :--- |
| `ai_agent_groq.py` | Core AI agent |
| `ai/multi_provider.py` | Provider fallback chain |
| `chat/agent.py` | Lya chat agent |
| `chat/safety.py` | Input/output guards |
| `rag/retriever.py` | Demo fast-path + context building |
| `multi_level_summary.py` | DevOps + Executive summaries |
| `test_integration.py` | Integration tests |
````