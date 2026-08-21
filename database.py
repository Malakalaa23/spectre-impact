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


init_db()
