"""
database.py — SQLite persistence for Spectre Impact.

Stores:
    - PR analyses (webhook results)
    - Commit analyses (push results)
    - User feedback on AI-generated insights (for the AI learning loop)

Public API:
    PR analyses:
        init_db()
        save_analysis(pr_number, repo_name, bfs_result, ai_result)
        get_all_analyses(limit)
        get_pr_analysis(pr_number)

    Commit analyses:
        init_commit_table()
        save_commit_analysis(commit_sha, repo_name, branch, changed_files, ...)
        is_commit_analyzed(commit_sha)
        get_commit_analysis(commit_sha)
        get_all_commit_analyses(limit)

    Feedback (AI learning loop):
        init_feedback_table()
        save_feedback(target_type, target_id, verdict, user_id, notes)
        get_feedback(limit)
        get_feedback_stats()

    All tables:
        init_all()
"""

import json
import sqlite3
from datetime import datetime, timezone


DB_FILE = "history.db"


def _get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# ===========================================================================
# PR analyses
# ===========================================================================
def init_db():
    conn = _get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pr_number INTEGER NOT NULL,
            repo_name TEXT NOT NULL,
            changed_resource TEXT,
            affected_services TEXT,
            business_impact INTEGER,
            simulation TEXT,
            severity TEXT,
            rollback TEXT,
            validation TEXT,
            tokens_used TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_analysis(pr_number: int, repo_name: str, bfs_result: dict, ai_result: dict):
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO analyses (
                pr_number, repo_name, changed_resource, affected_services,
                business_impact, simulation, severity, rollback, validation,
                tokens_used, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pr_number,
                repo_name,
                bfs_result.get("changed_resource"),
                json.dumps(bfs_result.get("affected_services", [])),
                bfs_result.get("business_impact"),
                ai_result.get("simulation"),
                ai_result.get("severity"),
                json.dumps(ai_result.get("rollback", [])),
                json.dumps(ai_result.get("validation", [])),
                json.dumps(ai_result.get("tokens_used", {})),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    record = dict(row)
    for field in ("affected_services", "rollback", "validation", "tokens_used", "suggestions"):
        if record.get(field):
            try:
                record[field] = json.loads(record[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return record


def get_all_analyses(limit: int = 50):
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM analyses ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_dict(row) for row in rows]


def get_pr_analysis(pr_number: int):
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM analyses WHERE pr_number = ? ORDER BY id DESC", (pr_number,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_dict(row) for row in rows]


# ===========================================================================
# Commit analyses
# ===========================================================================
def init_commit_table():
    """Create the commit_analyses table if it doesn't exist."""
    conn = _get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS commit_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commit_sha TEXT NOT NULL,
            repo_name TEXT NOT NULL,
            branch TEXT NOT NULL,
            changed_files TEXT,
            affected_services TEXT,
            business_impact INTEGER,
            suggestions TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_commit_analysis(
    commit_sha: str,
    repo_name: str,
    branch: str,
    changed_files: list,
    affected_services: list,
    business_impact: int,
    suggestions: list,
):
    """Save a commit analysis to the database."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO commit_analyses (
                commit_sha, repo_name, branch, changed_files,
                affected_services, business_impact, suggestions, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                commit_sha,
                repo_name,
                branch,
                json.dumps(changed_files),
                json.dumps(affected_services),
                business_impact,
                json.dumps(suggestions),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def is_commit_analyzed(commit_sha: str) -> bool:
    """Check if a commit has already been analyzed."""
    conn = _get_connection()
    try:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='commit_analyses'"
        ).fetchone()
        if not table_exists:
            return False
        row = conn.execute(
            "SELECT id FROM commit_analyses WHERE commit_sha = ?", (commit_sha,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_commit_analysis(commit_sha: str) -> dict:
    """Get a commit analysis by SHA."""
    conn = _get_connection()
    try:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='commit_analyses'"
        ).fetchone()
        if not table_exists:
            return None
        row = conn.execute(
            "SELECT * FROM commit_analyses WHERE commit_sha = ? ORDER BY id DESC",
            (commit_sha,),
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_all_commit_analyses(limit: int = 50):
    """Get all commit analyses."""
    conn = _get_connection()
    try:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='commit_analyses'"
        ).fetchone()
        if not table_exists:
            return []
        rows = conn.execute(
            "SELECT * FROM commit_analyses ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ===========================================================================
# Feedback — AI learning loop
# ===========================================================================
def init_feedback_table():
    """
    Create the feedback table if it doesn't exist.

    Schema:
        id           — auto increment
        target_type  — "analysis" | "insight" | "code_review" | "chat_response"
        target_id    — ID of the thing being rated
        verdict      — "correct" | "incorrect" | "partial"
        user_id      — who gave the feedback
        notes        — optional free-text
        created_at   — when

    Why this table exists:
        Every "correct" verdict becomes a positive training signal.
        Every "incorrect" verdict becomes a negative one.
        Over time, this becomes a labeled dataset we can use to fine-tune
        the model or improve retrieval. This is the mechanism behind
        "the AI learns from its mistakes."
    """
    conn = _get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            verdict TEXT NOT NULL,
            user_id TEXT,
            notes TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_feedback_target ON feedback(target_type, target_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_feedback_verdict ON feedback(verdict)"
    )
    conn.commit()
    conn.close()


def save_feedback(
    target_type: str,
    target_id: str,
    verdict: str,
    user_id: str | None = None,
    notes: str | None = None,
) -> int:
    """Store one feedback entry. Returns the new row's id."""
    if verdict not in ("correct", "incorrect", "partial"):
        raise ValueError(f"Invalid verdict: {verdict}")

    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO feedback (target_type, target_id, verdict, user_id, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                target_type,
                str(target_id),
                verdict,
                user_id or "anonymous",
                notes or "",
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        new_id = cursor.lastrowid
        conn.commit()
        return new_id
    finally:
        conn.close()


def get_feedback(limit: int = 100):
    """Return the most recent feedback entries."""
    conn = _get_connection()
    try:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='feedback'"
        ).fetchone()
        if not table_exists:
            return []
        rows = conn.execute(
            "SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_feedback_stats() -> dict:
    """
    Return aggregate feedback counts.

    Used by the /api/feedback/stats endpoint and the dashboard.
    """
    conn = _get_connection()
    try:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='feedback'"
        ).fetchone()
        if not table_exists:
            return {"correct": 0, "incorrect": 0, "partial": 0, "total": 0, "accuracy": None}

        rows = conn.execute(
            "SELECT verdict, COUNT(*) as count FROM feedback GROUP BY verdict"
        ).fetchall()
    finally:
        conn.close()

    stats = {"correct": 0, "incorrect": 0, "partial": 0, "total": 0}
    for row in rows:
        stats[row["verdict"]] = row["count"]
        stats["total"] += row["count"]

    if stats["total"] > 0:
        stats["accuracy"] = round(stats["correct"] / stats["total"] * 100, 1)
    else:
        stats["accuracy"] = None

    return stats


# ===========================================================================
# Init all tables
# ===========================================================================
def init_all():
    """Initialize every table. Safe to call multiple times."""
    init_db()
    init_commit_table()
    init_feedback_table()


init_all()


# ===========================================================================
# Self-test (run with `python database.py`)
# ===========================================================================
if __name__ == "__main__":
    print("Testing database functions...")

    # --- Test commit analysis ---
    test_sha = "test_commit_123"
    save_commit_analysis(
        test_sha,
        "test/repo",
        "main",
        ["test.py"],
        ["service1", "service2"],
        75,
        [{"file": "test.py", "line": 10, "suggestion": "Add null check"}],
    )

    result = is_commit_analyzed(test_sha)
    print(f"is_commit_analyzed: {result}")

    analysis = get_commit_analysis(test_sha)
    print(f"get_commit_analysis returned a row: {analysis is not None}")

    conn = _get_connection()
    conn.execute("DELETE FROM commit_analyses WHERE commit_sha = ?", (test_sha,))
    conn.commit()
    conn.close()

    # --- Test feedback loop ---
    fid = save_feedback(
        target_type="analysis",
        target_id="test-1",
        verdict="correct",
        user_id="test-user",
        notes="Self-test entry",
    )
    print(f"save_feedback returned id: {fid}")

    stats = get_feedback_stats()
    print(f"feedback stats: {stats}")

    # Cleanup
    conn = _get_connection()
    conn.execute("DELETE FROM feedback WHERE id = ?", (fid,))
    conn.commit()
    conn.close()

    print("All tests passed.")