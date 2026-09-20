"""Severity normalization layer for static analysis tools.

Normalizes Semgrep, Bandit, and Radon findings into consistent severity ratings
('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO') while preserving raw tool data.
"""

from __future__ import annotations

from typing import Any


def normalize_semgrep_severity(raw_severity: str) -> str:
    """Map Semgrep severity ('ERROR', 'WARNING', 'INFO') to standard string."""
    raw = (raw_severity or "").upper().strip()
    if raw == "ERROR":
        return "HIGH"
    if raw == "WARNING":
        return "MEDIUM"
    if raw in ("INFO", "LOW"):
        return "LOW"
    return "MEDIUM"


def normalize_bandit_severity(raw_severity: str) -> str:
    """Map Bandit severity ('HIGH', 'MEDIUM', 'LOW') to standard string."""
    raw = (raw_severity or "").upper().strip()
    if raw in ("HIGH", "MEDIUM", "LOW", "CRITICAL", "INFO"):
        return raw
    return "MEDIUM"


def normalize_radon_severity(rank_or_complexity: str | int) -> str:
    """Map Radon complexity rank ('A'-'F') or integer complexity to standard string."""
    if isinstance(rank_or_complexity, int):
        c = rank_or_complexity
        if c > 40:
            return "CRITICAL"
        if c > 20:
            return "HIGH"
        if c > 10:
            return "MEDIUM"
        if c > 5:
            return "LOW"
        return "INFO"

    rank = str(rank_or_complexity or "").upper().strip()
    if rank in ("F", "E"):
        return "HIGH"
    if rank in ("D", "C"):
        return "MEDIUM"
    if rank == "B":
        return "LOW"
    return "INFO"


def normalize_tool_findings(tool: str, raw_data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of raw_data with normalized severity annotations on findings."""
    if not isinstance(raw_data, dict):
        return {"status": "error", "error": "invalid raw data"}

    out = dict(raw_data)
    results = out.get("results")

    if not results or out.get("status") != "ok":
        return out

    if tool == "bandit" and isinstance(results, dict):
        findings = list(results.get("results", []))
        normalized_list = []
        for item in findings:
            item_copy = dict(item)
            item_copy["severity"] = normalize_bandit_severity(item.get("issue_severity", ""))
            normalized_list.append(item_copy)
        out["normalized_findings"] = normalized_list

    elif tool == "semgrep" and isinstance(results, dict):
        findings = list(results.get("results", []))
        normalized_list = []
        for item in findings:
            item_copy = dict(item)
            extra = item.get("extra", {})
            item_copy["severity"] = normalize_semgrep_severity(extra.get("severity", ""))
            normalized_list.append(item_copy)
        out["normalized_findings"] = normalized_list

    elif tool == "radon" and isinstance(results, dict):
        normalized_list = []
        for filename, entries in results.items():
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        item_copy = dict(entry)
                        item_copy["filename"] = filename
                        item_copy["severity"] = normalize_radon_severity(entry.get("rank", entry.get("complexity", 1)))
                        normalized_list.append(item_copy)
        out["normalized_findings"] = normalized_list

    return out
