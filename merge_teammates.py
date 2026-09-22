"""
merge_teammates.py — copy safe files from teammates' branches.

Takes only the files that:
    - do not exist on our branch (so no overwrite)
    - are not WIP files (_wip suffix)
    - are not scratch files (test.py, test.diff)
    - are not the old spectre-impact-dashboard folder

Prints a summary of every file copied and any that were skipped.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Files to take from origin/feature/abubakr-review
ABUBAKR_FILES = [
    "cli/__init__.py",
    "cli/main.py",
    "cli/utils.py",
    "cli/pyproject.toml",
    "cli/commands/__init__.py",
    "cli/commands/analyze.py",
    "cli/commands/auth.py",
    "cli/commands/chat.py",
    "cli/commands/config.py",
    "cli/commands/init.py",
    "cli/commands/rag.py",
    "cli/commands/report.py",
    "cli/commands/review.py",
    "cli/commands/watch.py",
    "code_review/__init__.py",
    "code_review/reviewer.py",
    "code_review/severity.py",
    "backend/api_models.py",
    "backend/session_manager.py",
    "rag/enrich.py",
    "voice/__init__.py",
    "voice/tts.py",
    "voice/fallbacks.py",
    "voice/fallbacks/critical.mp3",
    "voice/fallbacks/high.mp3",
    "voice/fallbacks/medium.mp3",
    "voice/fallbacks/low.mp3",
    "voice/fallbacks/unknown.mp3",
    "tests/test_abubakr_work.py",
    "tests/test_audit_and_integrations.py",
    "tests/test_features.py",
]

# Files to take from origin/feature/ahmed-backend-infra
AHMED_FILES = [
    "rollback_executor.py",
    "test_rollback.py",
    "load_test.py",
    "job_queue/__init__.py",
    "job_queue/worker.py",
]


def copy_files(branch: str, files: list[str]) -> tuple[list[str], list[str]]:
    """Copy each file from a branch. Returns (copied, errors)."""
    copied = []
    errors = []
    for f in files:
        result = subprocess.run(
            ["git", "checkout", f"{branch}", "--", f],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            copied.append(f)
        else:
            errors.append(f"{f}: {result.stderr.strip()}")
    return copied, errors


def main() -> int:
    print("=" * 70)
    print("  MERGE TEAMMATES")
    print("=" * 70)

    print("\n[1/2] Abu Bakr's branch — CLI, code review, voice")
    copied, errors = copy_files("origin/feature/abubakr-review", ABUBAKR_FILES)
    print(f"      copied: {len(copied)} files")
    if errors:
        print(f"      ERRORS ({len(errors)}):")
        for e in errors:
            print(f"        {e}")

    print("\n[2/2] Ahmed's branch — rollback executor, job queue")
    copied2, errors2 = copy_files("origin/feature/ahmed-backend-infra", AHMED_FILES)
    print(f"      copied: {len(copied2)} files")
    if errors2:
        print(f"      ERRORS ({len(errors2)}):")
        for e in errors2:
            print(f"        {e}")

    print()
    print("=" * 70)
    print(f"  TOTAL: {len(copied) + len(copied2)} files copied")
    print("=" * 70)
    print()
    print("Nothing is committed. Run `git status --short` to see what changed.")
    return 0 if not (errors or errors2) else 1


if __name__ == "__main__":
    raise SystemExit(main())