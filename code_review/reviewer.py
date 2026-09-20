"""Static + AI code review adapters.

Semgrep, Bandit, and Radon are optional executables. Missing tools are
reported as skipped results instead of crashing the API or CLI.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any
import os
import signal

from ai_agent_groq import generate_text


def _run(command: list[str], timeout: int = 60) -> dict[str, Any]:
    creationflags = 0

    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)

            stdout, stderr = proc.communicate()

            return {
                "status": "error",
                "error": f"{command[0]} timed out",
            }

    except FileNotFoundError:
        return {
            "status": "skipped",
            "error": f"{command[0]} is not installed",
        }

    stdout = stdout or ""
    stderr = stderr or ""

    if proc.returncode not in (0, 1, 2):
        return {
            "status": "error",
            "returncode": proc.returncode,
            "stderr": stderr[-4000:],
        }

    try:
        parsed = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        parsed = {"raw": stdout[-8000:]}

    return {
        "status": "ok",
        "returncode": proc.returncode,
        "results": parsed,
        "stderr": stderr[-2000:],
    }

def extract_changed_files(diff: str, repo_path: str | Path = ".") -> list[str]:
    """Extract real changed file paths from a unified diff."""

    root = Path(repo_path).resolve()
    files: list[str] = []

    for line in diff.splitlines():
        if not line.startswith("+++ "):
            continue

        path = line[4:].strip()

        # Skip deleted files.
        if path == "/dev/null":
            continue

        # Unified diffs normally use a/ and b/ prefixes.
        if path.startswith("b/"):
            path = path[2:]

        candidate = (root / path).resolve()

        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue

        if candidate.is_file():
            files.append(str(candidate))

    return list(dict.fromkeys(files))


def run_semgrep(
    path: str | Path | list[str] = ".",
) -> dict[str, Any]:
    if isinstance(path, list):
        command = ["semgrep", "--config=auto", "--json", *path]
    else:
        command = ["semgrep", "--config=auto", "--json", str(path)]

    return _run(command, timeout=120)


def run_bandit(
    path: str | Path | list[str] = ".",
) -> dict[str, Any]:
    command = [
        "bandit",
        "-f",
        "json",
        "--exclude",
        ".venv,venv,.git,node_modules,__pycache__,.pytest_cache,.mypy_cache",
    ]

    if isinstance(path, list):
        command.extend(path)
    else:
        command.extend(["-r", str(path)])

    return _run(command, timeout=120)


def run_radon(
    path: str | Path | list[str] = ".",
) -> dict[str, Any]:
    if isinstance(path, list):
        command = ["radon", "cc", "-s", "-j", *path]
    else:
        command = ["radon", "cc", "-s", "-j", str(path)]

    return _run(command, timeout=120)


def ai_code_review(diff: str) -> dict[str, Any]:
    prompt = """Review the following code diff for correctness, security,
reliability, and maintainability.

Return concise findings with:
- severity
- file/line when identifiable
- problem
- concrete fix

Do not claim a vulnerability unless the diff supports it.

DIFF:
""" + diff[:12000]

    try:
        response = generate_text(prompt)

        return {
            "status": "ok",
            "provider": response.provider,
            "model": response.model,
            "review": response.text,
        }

    except Exception as exc:
        return {
            "status": "unavailable",
            "review": "AI review unavailable.",
            "error": str(exc),
        }


def full_review(
    diff: str,
    repo_path: str | Path = ".",
) -> dict[str, Any]:
    """Run static analysis against files actually changed by the diff."""

    changed_files = extract_changed_files(diff, repo_path)

    if not changed_files:
        return {
            "semgrep": {
                "status": "skipped",
                "error": "No existing changed files found in diff.",
            },
            "bandit": {
                "status": "skipped",
                "error": "No existing changed files found in diff.",
            },
            "radon": {
                "status": "skipped",
                "error": "No existing changed files found in diff.",
            },
            "ai_review": ai_code_review(diff),
            "changed_files": [],
        }

    return {
        "semgrep": run_semgrep(changed_files),
        "bandit": run_bandit(changed_files),
        "radon": run_radon(changed_files),
        "ai_review": ai_code_review(diff),
        "changed_files": changed_files,
    }