#data.py
#
# DATA LAYER — the single source of truth for the whole dashboard.
#
# Rules this file follows (per the team's requirements):
# 1. NOTHING is a static hardcoded variable the UI reads directly.
#    The UI only ever calls functions: get_pr_data(), get_pr_details(),
#    get_metrics(), etc. Later, these functions can be rewritten to call
#    a real API/database instead of returning defaults, and NOT ONE LINE
#    in app.py or pages/*.py will need to change.
# 2. Backend field names are not trusted. Whatever shape of data comes in
#    (rollback vs rollback_plan, created_at vs timestamp, Impact vs
#    business_impact...) gets normalized into ONE standard internal
#    format before the UI ever sees it.
# 3. Nothing here ever raises an exception that could crash the app.
#    Missing/broken data becomes None or [] (safe, "empty" values) —
#    never a KeyError, never a crash. The UI decides how to display
#    "empty" (usually a friendly empty-state message).

import json
import os
import streamlit as st

try:
    import requests
except Exception:
    requests = None

from realtime import get_live_events


# =========================================================
# STANDARD INTERNAL PR FORMAT
# =========================================================
# Every PR record used anywhere in the app looks like this,
# no matter where it came from:
#
# {
#     "pr_number": "#445",
#     "repository": "Spectre",
#     "author": "Ahmed",
#     "severity": "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN",
#     "business_impact": 80 | None,
#     "affected_services": [...] | [],
#     "changed_files": [...] | [],
#     "simulation": [...] | [],
#     "rollback": [...] | [],
#     "validation": [...] | [],
#     "summary": "..." | None,
#     "created_at": "Aug 9, 2026" | None,
# }

VALID_SEVERITIES = {"HIGH", "MEDIUM", "LOW"}


def _first_present(raw, keys, default=None):
    """Return the value of the first key in `keys` that exists in `raw`
    and isn't None. Never raises, even if `raw` isn't a dict."""
    if not isinstance(raw, dict):
        return default
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    return default


def _normalize_severity(value):
    if not isinstance(value, str):
        return "UNKNOWN"
    upper = value.strip().upper()
    return upper if upper in VALID_SEVERITIES else "UNKNOWN"


def _normalize_impact(value):
    """Accepts 80, "80", "80%", or None/garbage -> returns int or None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "")
        if cleaned.isdigit():
            return int(cleaned)
    return None


def _normalize_list(value):
    """Anything that isn't a proper list of strings becomes an empty
    list, so the UI can always safely loop over it."""
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def normalize_pr(raw):
    """Convert ANY incoming PR-shaped dict into the standard internal
    format. Missing fields become None / [] rather than raising.
    Works even if `raw` is malformed or not a dict at all."""

    if not isinstance(raw, dict):
        raw = {}

    pr_number = _first_present(raw, ["pr_number", "PR", "number", "id"])
    if pr_number is not None and not str(pr_number).startswith("#"):
        pr_number = f"#{pr_number}"

    return {
        "pr_number": pr_number or "#UNKNOWN",
        "repository": _first_present(
            raw, ["repository", "repo_name", "repo", "Repository"], "Unknown Repository"
        ),
        "author": _first_present(
            raw, ["author", "developer", "user", "pr_author"], "Unknown"
        ),
        "severity": _normalize_severity(
            _first_present(raw, ["severity", "Severity", "risk", "risk_level"])
        ),
        "business_impact": _normalize_impact(
            _first_present(raw, ["business_impact", "impact", "Impact", "businessImpact"])
        ),
        "affected_services": _normalize_list(
            _first_present(raw, ["affected_services", "services", "Affected Services"])
        ),
        "changed_files": _normalize_list(
            _first_present(raw, ["changed_files", "files", "Changed Files"])
        ),
        "simulation": _normalize_list(
            _first_present(raw, ["simulation", "impact_simulation"])
        ),
        "rollback": _normalize_list(
            _first_present(raw, ["rollback", "rollback_plan"])
        ),
        "validation": _normalize_list(
            _first_present(raw, ["validation", "validation_checklist"])
        ),
        "summary": _first_present(raw, ["summary", "description", "ai_summary", "ai_analysis"]),
        "problem": _first_present(raw, ["problem", "potential_problem", "issue"]),
        "ai_analysis": _first_present(raw, ["ai_analysis", "ai_summary", "summary"]),
        "commit_message": _first_present(raw, ["commit_message", "commit", "title"]),
        "status": _first_present(raw, ["status", "state"], "analyzed"),
        "created_at": _first_present(raw, ["created_at", "timestamp", "date", "Date"]),
    }


# =========================================================
# BUILT-IN DEFAULT DATA
# =========================================================
# Used whenever nothing has been uploaded. This is what a brand new
# demo of the dashboard looks like out of the box.

_DEFAULT_RAW_PRS = [
    {
        "pr_number": "#445", "repository": "Spectre", "author": "Ahmed",
        "severity": "HIGH", "business_impact": 80,
        "affected_services": ["Login Service", "Payment Gateway", "Main Database"],
        "changed_files": ["database.tf", "login.py", "docker-compose.yml"],
        "simulation": [
            "Database migration fails", "Login service loses connection",
            "Checkout requests timeout", "Customers cannot purchase"
        ],
        "rollback": [
            "Revert the database migration", "Restart the login service",
            "Verify database connectivity"
        ],
        "validation": ["curl /health", "kubectl get pods", "Check application logs"],
        "summary": (
            "Payment service experienced elevated latency due to expired "
            "TLS certificates. Pods required restart."
        ),
        "created_at": "Aug 9, 2026",
    },
    {
        "pr_number": "#443", "repository": "Spectre", "author": "Malak",
        "severity": "HIGH", "business_impact": 75,
        "affected_services": ["Login Service", "Authentication", "API Gateway"],
        "changed_files": ["auth_middleware.py", "session_manager.py"],
        "simulation": [
            "Auth middleware deploys", "Session tokens fail validation",
            "Users get logged out unexpectedly", "Support tickets spike"
        ],
        "rollback": [
            "Revert the auth middleware change",
            "Invalidate and reissue affected sessions",
            "Confirm login success rate returns to normal"
        ],
        "validation": ["Check login success rate", "kubectl get pods", "Review auth logs"],
        "summary": (
            "A change to the authentication middleware caused intermittent "
            "401 errors for a subset of active sessions."
        ),
        "created_at": "Aug 9, 2026",
    },
    {
        "pr_number": "#442", "repository": "Spectre", "author": "Abu Bakr",
        "severity": "MEDIUM", "business_impact": 45,
        "affected_services": ["API Gateway", "Authentication"],
        "changed_files": ["gateway_config.yaml"],
        "simulation": [
            "New rate limits deploy", "Peak-hour traffic approaches the new threshold",
            "Some legitimate requests get throttled"
        ],
        "rollback": [
            "Revert rate-limit thresholds to previous values",
            "Monitor gateway error rate for 15 minutes"
        ],
        "validation": ["Monitor 429 error rate", "curl /health"],
        "summary": (
            "API Gateway rate-limit thresholds were tightened, which may "
            "throttle legitimate traffic during peak hours."
        ),
        "created_at": "Aug 8, 2026",
    },
    {
        "pr_number": "#441", "repository": "Auth-Gateway", "author": "Habiba",
        "severity": "LOW", "business_impact": 15,
        "affected_services": ["Authentication"],
        "changed_files": ["logging_config.py"],
        "simulation": [
            "Logging change deploys", "Log verbosity increases slightly",
            "No impact on request handling"
        ],
        "rollback": ["Revert the logging configuration"],
        "validation": ["Check log output format"],
        "summary": (
            "Minor logging changes to the Auth-Gateway service. No "
            "functional behavior was modified."
        ),
        "created_at": "Aug 8, 2026",
    },
    {
        "pr_number": "#440", "repository": "Payment-Service", "author": "Merna",
        "severity": "MEDIUM", "business_impact": 40,
        "affected_services": ["Payment Gateway", "Main Database"],
        "changed_files": ["retry_policy.py", "payment_client.py"],
        "simulation": [
            "New retry policy deploys", "Failed payments retry with backoff",
            "Checkout latency increases slightly"
        ],
        "rollback": [
            "Revert to the previous retry policy",
            "Verify checkout latency returns to baseline"
        ],
        "validation": ["Monitor checkout latency", "curl /health"],
        "summary": (
            "Payment retry logic was updated to add exponential backoff, "
            "slightly increasing checkout latency."
        ),
        "created_at": "Aug 7, 2026",
    },
]

DEFAULT_PRS = [normalize_pr(pr) for pr in _DEFAULT_RAW_PRS]

# Sample weekly risk trend, used only when no real historical data has
# been uploaded. Clearly a placeholder — every chart that uses it says
# so in a caption.
DEFAULT_WEEKLY_TREND = [
    {"week": "W1", "high": 2, "medium": 3, "low": 4},
    {"week": "W2", "high": 3, "medium": 4, "low": 3},
    {"week": "W3", "high": 4, "medium": 3, "low": 5},
    {"week": "W4", "high": 3, "medium": 5, "low": 4},
    {"week": "W5", "high": 5, "medium": 4, "low": 3},
    {"week": "W6", "high": 6, "medium": 5, "low": 3},
]


# =========================================================
# UPLOAD HANDLING
# =========================================================
# The uploader itself lives in the sidebar (style.py) so it's visible on
# every page, all the time. This is the function it calls.

def set_uploaded_pr_data(uploaded_file):
    """Try to load a JSON file the user uploaded. Accepts either:
      - a plain list of PR records:            [ {...}, {...} ]
      - a dict with "prs" (and optional
        "weekly_trend"):  { "prs": [...], "weekly_trend": [...] }

    Every record is normalized individually, so a file with some good
    records and some broken ones still loads the good parts. If the
    file can't even be read as JSON, nothing changes — the app keeps
    using whatever data source it had before (defaults, most likely).

    Returns (success: bool, message: str) — never raises.
    """
    try:
        raw_text = uploaded_file.read()
        parsed = json.loads(raw_text)
    except Exception:
        return False, (
            "⚠️ Couldn't read that file as JSON. Keeping the current data."
        )

    weekly_trend = None

    if isinstance(parsed, dict):
        records = parsed.get("prs", [])
        weekly_trend = parsed.get("weekly_trend")
    elif isinstance(parsed, list):
        records = parsed
    else:
        return False, (
            "⚠️ That file's format isn't recognized. Keeping the current data."
        )

    if not isinstance(records, list) or len(records) == 0:
        return False, (
            "⚠️ No PR records found in that file. Keeping the current data."
        )

    normalized = [normalize_pr(r) for r in records]

    st.session_state["uploaded_pr_data"] = normalized
    st.session_state["upload_filename"] = getattr(uploaded_file, "name", "uploaded file")

    if isinstance(weekly_trend, list) and len(weekly_trend) > 0:
        st.session_state["uploaded_weekly_trend"] = weekly_trend

    return True, f"✅ Loaded {len(normalized)} PR record(s) from {st.session_state['upload_filename']}."


def clear_uploaded_data():
    st.session_state.pop("uploaded_pr_data", None)
    st.session_state.pop("upload_filename", None)
    st.session_state.pop("uploaded_weekly_trend", None)


def has_uploaded_data():
    return bool(st.session_state.get("uploaded_pr_data"))


# =========================================================
# PUBLIC DATA API — this is what every page actually calls
# =========================================================

def _remote_prs():
    """Optional remote PR source. Any network failure falls back cleanly."""
    base = os.getenv("SPECTRE_DATA_API_URL", "").strip().rstrip("/")
    if not base or requests is None:
        return None
    try:
        response = requests.get(f"{base}/prs", timeout=2.5)
        response.raise_for_status()
        payload = response.json()
        records = payload.get("prs") if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            return None
        return [normalize_pr(record) for record in records]
    except Exception:
        return None


def _merge_live_events(prs):
    """Turn webhook events into PR records so new changes appear immediately."""
    merged = {pr["pr_number"]: dict(pr) for pr in prs}
    try:
        events = get_live_events(limit=100)
    except Exception:
        events = []
    for event in events:
        number = event.get("pr_number")
        if not number:
            continue
        normalized = normalize_pr({
            "pr_number": number,
            "repository": event.get("repository"),
            "author": event.get("author"),
            "severity": event.get("severity"),
            "affected_services": event.get("affected_services"),
            "changed_files": event.get("changed_files"),
            "summary": event.get("ai_analysis") or event.get("problem"),
            "problem": event.get("problem"),
            "ai_analysis": event.get("ai_analysis"),
            "commit_message": event.get("commit_message"),
            "status": event.get("status"),
            "created_at": event.get("timestamp"),
        })
        existing = merged.get(number)
        if existing:
            existing.update({k: v for k, v in normalized.items() if v not in (None, [], "UNKNOWN")})
        else:
            merged[number] = normalized
    return list(merged.values())


def get_pr_data():
    """Return uploaded, remote, or demo PR data, merged with live webhook events."""
    uploaded = st.session_state.get("uploaded_pr_data")
    if uploaded:
        return _merge_live_events(uploaded)
    remote = _remote_prs()
    if remote:
        return _merge_live_events(remote)
    return _merge_live_events(DEFAULT_PRS)


def get_pr_details(pr_number):
    """Find one PR by number. Accepts "#445", "445", or 445.
    If it isn't found, returns a safe empty record instead of raising,
    with an extra "found": False flag the UI can check."""

    if pr_number is None:
        target = None
    else:
        target = str(pr_number)
        if not target.startswith("#"):
            target = f"#{target}"

    for pr in get_pr_data():
        if pr["pr_number"] == target:
            result = dict(pr)
            result["found"] = True
            return result

    empty = normalize_pr({})
    empty["pr_number"] = target or "#UNKNOWN"
    empty["found"] = False
    return empty


def get_metrics():
    """KPI counts, always computed live from whatever PR data is
    currently active -- never hardcoded numbers."""
    prs = get_pr_data()
    return {
        "total": len(prs),
        "high": sum(1 for pr in prs if pr["severity"] == "HIGH"),
        "medium": sum(1 for pr in prs if pr["severity"] == "MEDIUM"),
        "low": sum(1 for pr in prs if pr["severity"] == "LOW"),
    }


def get_repository_distribution():
    """{repository_name: pr_count}, derived live from the active data."""
    counts = {}
    for pr in get_pr_data():
        repo = pr["repository"] or "Unknown Repository"
        counts[repo] = counts.get(repo, 0) + 1
    return counts


def get_risk_distribution():
    """{severity: pr_count}, derived live from the active data."""
    metrics = get_metrics()
    dist = {"HIGH": metrics["high"], "MEDIUM": metrics["medium"], "LOW": metrics["low"]}
    unknown = metrics["total"] - sum(dist.values())
    if unknown > 0:
        dist["UNKNOWN"] = unknown
    return dist


def get_affected_services_distribution():
    """{service_name: number_of_prs_mentioning_it}, derived live."""
    counts = {}
    for pr in get_pr_data():
        for service in pr["affected_services"]:
            counts[service] = counts.get(service, 0) + 1
    return counts


def get_risk_trend():
    """Weekly risk trend. Uses uploaded historical data if present,
    otherwise a clearly-labeled sample trend (there's no way to build a
    real week-by-week history from a single snapshot of PR records)."""
    trend = st.session_state.get("uploaded_weekly_trend")
    is_sample = trend is None
    if trend is None:
        trend = DEFAULT_WEEKLY_TREND
    return trend, is_sample


def get_recent_activity(limit=5):
    """Most recent PR records, for the Developer dashboard's live feed."""
    return get_pr_data()[:limit]