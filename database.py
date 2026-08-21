import json
import sqlite3
from datetime import datetime, timezone

DB_FILE = "history.db"


def _get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


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
    for field in ("affected_services", "rollback", "validation", "tokens_used"):
        if record.get(field):
            record[field] = json.loads(record[field])
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


# ============================================================
# NEW: Commit analysis functions (for inline feedback)
# ============================================================

def init_commit_table():
    """Create the commit_analyses table if it doesn't exist"""
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


def save_commit_analysis(commit_sha: str, repo_name: str, branch: str,
                         changed_files: list, affected_services: list,
                         business_impact: int, suggestions: list):
    """
    Save a commit analysis to the database.
    """
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
                datetime.now(timezone.utc).isoformat()
            )
        )
        conn.commit()
    finally:
        conn.close()


def is_commit_analyzed(commit_sha: str) -> bool:
    """
    Check if a commit has already been analyzed.
    """
    conn = _get_connection()
    try:
        # Check if the table exists first
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
    """
    Get a commit analysis by SHA.
    """
    conn = _get_connection()
    try:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='commit_analyses'"
        ).fetchone()
        if not table_exists:
            return None
        row = conn.execute(
            "SELECT * FROM commit_analyses WHERE commit_sha = ? ORDER BY id DESC", (commit_sha,)
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_all_commit_analyses(limit: int = 50):
    """
    Get all commit analyses.
    """
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


# ============================================================
# Initialize tables on module load
# ============================================================
init_db()
init_commit_table()

# ============================================================
# Quick self‑test (run with `python database.py`)
# ============================================================
if __name__ == "__main__":
    print("🧪 Testing database functions...")
    
    # Test commit functions
    test_sha = "test_commit_123"
    save_commit_analysis(
        test_sha,
        "test/repo",
        "main",
        ["test.py"],
        ["service1", "service2"],
        75,
        [{"file": "test.py", "line": 10, "suggestion": "Add null check"}]
    )
    
    result = is_commit_analyzed(test_sha)
    print(f"✅ is_commit_analyzed: {result}")
    
    analysis = get_commit_analysis(test_sha)
    print(f"✅ get_commit_analysis: {analysis is not None}")
    
    # Clean up
    conn = _get_connection()
    conn.execute("DELETE FROM commit_analyses WHERE commit_sha = ?", (test_sha,))
    conn.commit()
    conn.close()
    
    print("✅ All tests passed!")