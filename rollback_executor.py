"""Safe rollback executor.

Validates a command against a whitelist before it's ever run, supports
a dry-run mode that reports what *would* happen without executing, and
logs every attempt — allowed, blocked, or executed — to the audit table.

Uses re.fullmatch (not re.match) against the whitelist so a command like
"kubectl rollout undo deployment/foo; rm -rf /" gets blocked outright —
re.match alone only anchors the start of the string and would have let
the appended command slip through.
"""

import re
import subprocess
from dataclasses import dataclass
from typing import List

from database import get_connection

# Only these exact shapes are ever allowed to execute. Extend deliberately —
# anything not matched here is blocked by default.
WHITELIST_PATTERNS = [
    r"kubectl rollout undo deployment/[\w-]+(\s+--to-revision=\d+)?",
    r"docker service update --rollback [\w-]+",
    r"git revert --no-edit [0-9a-f]{7,40}",
]

DANGEROUS_SUBSTRINGS = ["rm -rf", ":(){ :|:& };:", "> /dev/sda", "mkfs", "dd if="]


@dataclass
class ValidationResult:
    safe: bool
    reason: str


def validate_command(command: str) -> ValidationResult:
    command = command.strip()

    for bad in DANGEROUS_SUBSTRINGS:
        if bad in command:
            return ValidationResult(safe=False, reason=f"matched dangerous pattern: {bad}")

    for pattern in WHITELIST_PATTERNS:
        if re.fullmatch(pattern, command):
            return ValidationResult(safe=True, reason="matched whitelist")

    return ValidationResult(safe=False, reason="not in whitelist")


def _log(command: str, dry_run: bool, status: str, output: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO rollback_audit_log (command, dry_run, status, output) "
                "VALUES (%s, %s, %s, %s);",
                (command, dry_run, status, output),
            )


def execute_rollback(commands: List[str], dry_run: bool = True) -> dict:
    results = []
    for command in commands:
        check = validate_command(command)
        if not check.safe:
            _log(command, dry_run, "blocked", check.reason)
            results.append({"command": command, "status": "blocked", "reason": check.reason})
            continue

        if dry_run:
            _log(command, dry_run, "dry_run_ok", "")
            results.append({"command": command, "status": "dry_run_ok"})
            continue

        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30
            )
            status = "success" if proc.returncode == 0 else "failed"
            output = proc.stdout + proc.stderr
        except subprocess.TimeoutExpired:
            status, output = "failed", "timed out after 30s"

        _log(command, dry_run, status, output)
        results.append({"command": command, "status": status, "output": output})

    return {"results": results}
