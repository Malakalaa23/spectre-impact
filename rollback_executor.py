"""Safe rollback executor.

Validates a command against a whitelist before it's ever run, supports
a dry-run mode that reports what *would* happen without executing, and
logs every attempt — allowed, blocked, or executed — to the audit table.

Uses re.fullmatch (not re.match) against the whitelist so a command like
"kubectl rollout undo deployment/foo; rm -rf /" gets blocked outright —
re.match alone only anchors the start of the string and would have let
the appended command slip through.

Database:
    Uses the same SQLite connection helper as the rest of Spectre
    Impact (`database._get_connection`). The audit table is created
    by `database.init_all()` at import time, so callers do not need
    to initialize anything.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from typing import List

from database import _get_connection


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Whitelist
# ---------------------------------------------------------------------------
# Only these exact shapes are ever allowed to execute. Extend deliberately —
# anything not matched here is blocked by default.
WHITELIST_PATTERNS = [
    r"kubectl rollout undo deployment/[\w-]+(\s+--to-revision=\d+)?",
    r"docker service update --rollback [\w-]+",
    r"git revert --no-edit [0-9a-f]{7,40}",
]

DANGEROUS_SUBSTRINGS = ["rm -rf", ":(){ :|:& };:", "> /dev/sda", "mkfs", "dd if="]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
@dataclass
class ValidationResult:
    safe: bool
    reason: str


def validate_command(command: str) -> ValidationResult:
    """
    Return whether the command is safe to execute.

    Two-stage check:
        1. Refuse anything containing a known-destructive substring.
        2. Accept only if the entire command matches one whitelist pattern
           via re.fullmatch (which anchors both ends of the string).

    A blocked command gets a human-readable reason for the audit log.
    """
    command = (command or "").strip()

    if not command:
        return ValidationResult(safe=False, reason="empty command")

    for bad in DANGEROUS_SUBSTRINGS:
        if bad in command:
            return ValidationResult(safe=False, reason=f"matched dangerous pattern: {bad}")

    for pattern in WHITELIST_PATTERNS:
        if re.fullmatch(pattern, command):
            return ValidationResult(safe=True, reason="matched whitelist")

    return ValidationResult(safe=False, reason="not in whitelist")


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
def _log(command: str, dry_run: bool, status: str, output: str) -> None:
    """
    Append one row to rollback_audit_log. Failures here are logged but
    never raised — the audit trail should not block a rollback.
    """
    try:
        conn = _get_connection()
        try:
            conn.execute(
                "INSERT INTO rollback_audit_log "
                "(command, dry_run, status, output) VALUES (?, ?, ?, ?)",
                (command, 1 if dry_run else 0, status, output or ""),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("rollback audit log write failed: %s", exc)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
def execute_rollback(commands: List[str], dry_run: bool = True) -> dict:
    """
    Validate and (optionally) execute a list of rollback commands.

    Args:
        commands: The list of shell commands to run.
        dry_run:  If True, validate and log but never actually execute.
                  Defaults to True so a caller must opt in to real runs.

    Returns:
        {"results": [{"command": ..., "status": ..., "reason"/"output": ...}]}
        status is one of: "blocked", "dry_run_ok", "success", "failed".
    """
    results: list[dict] = []

    for command in commands:
        check = validate_command(command)

        if not check.safe:
            _log(command, dry_run, "blocked", check.reason)
            results.append({
                "command": command,
                "status": "blocked",
                "reason": check.reason,
            })
            continue

        if dry_run:
            _log(command, dry_run, "dry_run_ok", "")
            results.append({"command": command, "status": "dry_run_ok"})
            continue

        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            status = "success" if proc.returncode == 0 else "failed"
            output = (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired:
            status, output = "failed", "timed out after 30s"
        except Exception as exc:  # noqa: BLE001
            status, output = "failed", f"execution error: {exc}"

        _log(command, dry_run, status, output)
        results.append({"command": command, "status": status, "output": output})

    return {"results": results}