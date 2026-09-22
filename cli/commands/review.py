from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from code_review.reviewer import full_review

console = Console()


def _print_findings(tool: str, result: dict) -> None:
    status = result.get("status", "unknown")

    if status == "skipped":
        console.print(f"[yellow]{tool}:[/] skipped — {result.get('error', '')}")
        return

    if status == "error":
        console.print(f"[red]{tool}:[/] error — {result.get('error', '')}")
        return

    console.print(f"[green]{tool}:[/] ok")

    results = result.get("results", {})

    if not results:
        return

    findings = []

    if tool == "bandit":
        findings = results.get("results", [])

    elif tool == "semgrep":
        findings = results.get("results", [])

    elif tool == "radon":
        findings = []

        if isinstance(results, dict):
            for filename, entries in results.items():
                for entry in entries:
                    findings.append(
                        {
                            "filename": filename,
                            "line": entry.get("lineno"),
                            "severity": "INFO",
                            "message": (
                                f"Complexity {entry.get('complexity')} "
                                f"({entry.get('rank')}) in "
                                f"{entry.get('name')}"
                            ),
                        }
                    )

    if not findings:
        return

    table = Table(title=f"{tool.title()} Findings")

    table.add_column("Severity")
    table.add_column("File")
    table.add_column("Line")
    table.add_column("Finding")

    for finding in findings:
        if tool == "bandit":
            severity = finding.get("issue_severity", "UNKNOWN")
            filename = str(Path(finding.get("filename", "")).name)
            line = str(finding.get("line_number", ""))
            message = finding.get("issue_text", "")

        elif tool == "semgrep":
            extra = finding.get("extra", {})
            severity = extra.get("severity", "UNKNOWN")
            filename = str(Path(finding.get("path", "")).name)
            start = finding.get("start", {})
            line = str(start.get("line", ""))
            message = extra.get("message", "")

        else:
            severity = finding["severity"]
            filename = finding["filename"]
            line = str(finding.get("line", ""))
            message = finding["message"]

        table.add_row(
            severity,
            filename,
            line,
            message,
        )

    console.print(table)


def run(
    diff_file: str = typer.Argument(..., help="File containing a unified diff"),
    repo_path: str = typer.Option("."),
) -> None:
    path = Path(diff_file)

    if not path.exists():
        raise typer.BadParameter(f"Diff file not found: {path}")

    diff = path.read_text(encoding="utf-8", errors="ignore")

    result = full_review(diff, repo_path)

    for tool in ("semgrep", "bandit", "radon"):
        _print_findings(tool, result[tool])

    ai = result["ai_review"]
    raw_review = ai.get("review", "AI review unavailable.")
    from chat.safety import sanitize_output

    console.print(
        Panel(
            sanitize_output(raw_review),
            title="AI Code Review",
        )
    )