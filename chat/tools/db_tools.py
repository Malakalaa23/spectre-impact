"""
db_tools.py — Tools that expose the Spectre Impact database to the agent.

These tools let Lya answer questions like:
    - "Show me past PRs that affected payment_service"
    - "What happened in PR #445?"
    - "Any critical incidents in the last week?"

They wrap functions from `database.py`, which reads from SQLite (history.db).

Public API:
    get_past_prs          — find past PRs that touched a service.
    get_pr_details        — fetch full analysis for a PR number.
    get_recent_incidents  — list critical/high severity items.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from database import get_all_analyses, get_pr_analysis


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _safe_json_load(value: Any) -> Any:
    """
    history.db stores list/dict fields as JSON strings. Decode if needed.
    """
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        import json
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def _row_to_summary(row: dict) -> str:
    """Format one analysis row as a compact human-readable line."""
    pr = row.get("pr_number", "?")
    severity = row.get("severity", "unknown")
    impact = row.get("business_impact", 0)
    resource = row.get("changed_resource", "unknown")
    created = row.get("created_at", "")
    return f"PR #{pr} [{severity}] — {resource} ({impact}% impact) @ {created}"


# ---------------------------------------------------------------------------
# Tool 1: get_past_prs
# ---------------------------------------------------------------------------
@tool
def get_past_prs(service_name: str) -> str:
    """
    Find past PRs that affected a specific service, API, or journey.

    Use this when the user asks:
        "What past PRs affected payment_service?"
        "Show me the history for the checkout API"
        "Has anyone touched the login service before?"

    Args:
        service_name: The name of the service (e.g. "payment_service",
                      "checkout_api", "web_frontend").

    Returns:
        A list of past PRs that affected the service, with severity,
        business impact, and changed resource for each.
    """
    if not service_name or not service_name.strip():
        return "No service name provided."

    target = service_name.strip()

    try:
        analyses = get_all_analyses(limit=200)
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_past_prs failed")
        return f"Database query failed: {exc}"

    matching: list[dict] = []
    for row in analyses:
        affected = _safe_json_load(row.get("affected_services")) or []
        if target in affected:
            matching.append(row)

    if not matching:
        return f"No past PRs found that affected '{target}'."

    lines = [f"Found {len(matching)} past PR(s) affecting '{target}':", ""]
    # Show up to 10 most recent
    for row in matching[:10]:
        lines.append(_row_to_summary(row))
    if len(matching) > 10:
        lines.append(f"... and {len(matching) - 10} more")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 2: get_pr_details
# ---------------------------------------------------------------------------
@tool
def get_pr_details(pr_number: int) -> str:
    """
    Get the full analysis for a specific PR number.

    Use this when the user asks:
        "What happened in PR #445?"
        "Show me the details of PR 12"
        "What was the rollback plan for PR #88?"

    Args:
        pr_number: The pull request number (e.g. 445).

    Returns:
        Full details: severity, business impact, changed resource,
        affected services, simulation, rollback plan, and validation steps.
    """
    try:
        rows = get_pr_analysis(int(pr_number))
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_pr_details failed")
        return f"Database query failed: {exc}"

    if not rows:
        return f"No analysis found for PR #{pr_number}."

    row = rows[0]
    affected = _safe_json_load(row.get("affected_services")) or []
    rollback = _safe_json_load(row.get("rollback")) or []
    validation = _safe_json_load(row.get("validation")) or []

    lines = [
        f"PR #{row.get('pr_number')} — {row.get('severity', 'unknown')} severity",
        f"Repository: {row.get('repo_name', 'unknown')}",
        f"Changed resource: {row.get('changed_resource', 'unknown')}",
        f"Business impact: {row.get('business_impact', 0)}%",
        f"Created: {row.get('created_at', 'unknown')}",
        "",
        f"Affected services ({len(affected)}):",
    ]
    for service in affected[:15]:
        lines.append(f"  - {service}")
    if len(affected) > 15:
        lines.append(f"  ... and {len(affected) - 15} more")

    if row.get("simulation"):
        lines.append("")
        lines.append("AI Simulation:")
        lines.append(f"  {row['simulation']}")

    if rollback:
        lines.append("")
        lines.append("Rollback plan:")
        for step in rollback[:10]:
            lines.append(f"  - {step}")

    if validation:
        lines.append("")
        lines.append("Validation steps:")
        for step in validation[:10]:
            lines.append(f"  - {step}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 3: get_recent_incidents
# ---------------------------------------------------------------------------
@tool
def get_recent_incidents(days: int = 7) -> str:
    """
    List recent critical and high-severity PRs.

    Use this when the user asks:
        "What incidents happened this week?"
        "Any critical changes recently?"
        "Show me high-risk PRs from the last 14 days"

    Args:
        days: Look back this many days. Default is 7.

    Returns:
        A list of critical/high severity analyses from the recent past.
    """
    from datetime import datetime, timedelta, timezone

    try:
        analyses = get_all_analyses(limit=200)
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_recent_incidents failed")
        return f"Database query failed: {exc}"

    # Filter by severity
    severe = [
        row for row in analyses
        if (row.get("severity") or "").upper() in ("CRITICAL", "HIGH")
    ]

    if not severe:
        return "No critical or high-severity incidents found in recent history."

    lines = [f"Found {len(severe)} critical/high-severity item(s):", ""]
    for row in severe[:10]:
        lines.append(_row_to_summary(row))
    if len(severe) > 10:
        lines.append(f"... and {len(severe) - 10} more")

    return "\n".join(lines)


__all__ = ["get_past_prs", "get_pr_details", "get_recent_incidents"]