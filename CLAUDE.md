# Spectre Impact

## Architecture: two webhook pipelines, shared core logic

Both pipelines share `calculate_blast_radius()` and `generate_insights()`. They diverge at the trigger and the persistence/notification step.

**`pull_request` (action == "opened")** — `main.py`
```
fetch_changed_files → calculate_blast_radius → generate_insights → save_analysis → post_github_comment
```
Fully working, tested. **DO NOT MODIFY without explicit confirmation.**

**`push`** — `main.py`
```
parse_push_payload → calculate_blast_radius → generate_insights → save_commit_analysis
```
Verified end-to-end via a real webhook payload on 2026-08-21 — confirmed a row lands correctly in `commit_analyses` with real blast-radius and AI-insight data.

Inline GitHub comment posting is **intentionally disabled** (see Known Issues — `post_inline_comment` position bug). The pipeline still runs and saves to the DB; it just doesn't post to GitHub.

`GET /api/commit-analyses` now exists (mirrors `/api/analyses`) — returns `commit_analyses` rows with JSON-decoded fields (`changed_files`, `affected_services`, `suggestions`). Verified via a real inserted-then-deleted test row on 2026-08-21.

## Known issues — deliberate, do not "fix" without asking first

- **`github_client.py` — `post_inline_comment`**: passes a file line number as GitHub's comment `position`, but GitHub expects an offset into the diff hunk, not a file line number. Broken for any multi-hunk diff. This is why the push pipeline's call to `post_inline_comment` is currently disabled in `main.py`.
- **`diff_parser.py` — `parse_unified_diff`**: never populates `removed_lines` (initialized but never appended to). Harmless — nothing downstream reads it.
- **`main.py` — `is_commit_analyzed`**: checked before `save_commit_analysis` runs (after network calls), so a redelivered webhook could theoretically create duplicate rows. Not fixed — low priority.
- **`main.py` — `parse_push_payload`**: only reads `payload["head_commit"]`, not `payload["commits"]` — a multi-commit push only analyzes the last commit's files.
- **`main.py` — branch parsing**: only strips `refs/heads/`, so tag pushes leave `branch` as `refs/tags/...`. Not handled.
- **`run_push_analysis_pipeline`**: duplicates blast-radius/insights/fallback logic from `run_analysis_pipeline` verbatim — refactor opportunity, not urgent.

## Database

`analyses` (PR-keyed) and `commit_analyses` (commit-sha-keyed) are **intentionally separate** — they key on different things (PR number vs. commit SHA; a push can happen with no open PR). Merging would produce a wide, mostly-null schema. Keep separate.

## Environment

**DONE** — `./venv` exists, `requirements.txt` has 36 pinned packages generated via `pip freeze` inside the activated venv. Verified: server boots correctly via `./venv/Scripts/python.exe`.

- Always activate `./venv` before `pip install`ing anything — confirm with `pip show <package>` that `Location` points inside `venv/`, not global site-packages.
- Re-freeze `requirements.txt` via `pip freeze > requirements.txt` (inside the activated venv) after adding any new dependency.
- `check_installed.py` lists a broader expected package set (14 packages, including dashboard/backend-only ones like streamlit/pandas/plotly/networkx/matplotlib/httpx/pytest not needed by the root pipeline) — useful for checking the dashboard/backend folders specifically, not the root venv.

## Other repo notes — unresolved

- `backend/` has a separate, more complete BFS/dependency-graph implementation (`backend/analysis/*`) that is **not wired into root `main.py`**. Root `main.py` has its own simpler inline `calculate_blast_radius`. Two parallel implementations exist; not reconciled.
- Two near-identical dashboard folders: `dashboard/` and `spectre-impact-dashboard/`, same file names throughout. Unclear if one is stale. Not resolved.
- `ai_agent.py` exists alongside `ai_agent_groq.py` — `main.py` only imports from `ai_agent_groq.py`, so `ai_agent.py` appears unused. It uses different dependencies (`google-genai`, `pydantic`), which got pulled into `requirements.txt` during the dependency scan even though nothing currently calls it.
- **Pattern across all three**: `backend/` vs. root pipeline, `dashboard/` vs. `spectre-impact-dashboard/`, and `ai_agent.py` vs. `ai_agent_groq.py` are the same kind of unresolved duplication — three+ places in this repo where an alternate/newer implementation may exist but isn't wired in. Needs a deliberate decision pass (not tonight) on which version of each is authoritative before final submission.
