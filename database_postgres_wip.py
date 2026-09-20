# WORK IN PROGRESS — Postgres migration, not yet merged into the
# live database.py/main.py pending a team decision on reconciling
# with the existing SQLite push-pipeline. Do not import or use this
# file directly until that decision is made.

"""Postgres connection + schema for Spectre Impact.

Replaces the original SQLite implementation. Call init_db() once at
startup (e.g. in main.py's startup event) before any reads/writes.
Function names match the original SQLite version so main.py shouldn't
need changes beyond adding the init_db() call.
"""

import json
import os
from contextlib import contextmanager

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://spectre:password@localhost:5432/spectre_impact",
)


@contextmanager
def get_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id SERIAL PRIMARY KEY,
                    pr_number INTEGER NOT NULL,
                    repo_name TEXT NOT NULL,
                    changed_resource TEXT,
                    affected_services JSONB,
                    business_impact INTEGER,
                    simulation TEXT,
                    severity TEXT,
                    rollback JSONB,
                    validation JSONB,
                    tokens_used JSONB,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS commit_analyses (
                    id SERIAL PRIMARY KEY,
                    commit_sha TEXT NOT NULL,
                    repo_name TEXT NOT NULL,
                    changed_resource TEXT,
                    affected_services JSONB,
                    business_impact TEXT,
                    simulation TEXT,
                    severity TEXT,
                    rollback JSONB,
                    validation JSONB,
                    tokens_used INTEGER,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rollback_audit_log (
                    id SERIAL PRIMARY KEY,
                    command TEXT NOT NULL,
                    dry_run BOOLEAN NOT NULL,
                    status TEXT NOT NULL,
                    output TEXT,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
                """
            )


def save_analysis(pr_number: int, repo_name: str, bfs_result: dict, ai_result: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analyses (
                    pr_number, repo_name, changed_resource, affected_services,
                    business_impact, simulation, severity, rollback,
                    validation, tokens_used
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    pr_number,
                    repo_name,
                    bfs_result.get("changed_resource"),
                    json.dumps(bfs_result.get("affected_services")),
                    bfs_result.get("business_impact"),
                    ai_result.get("simulation"),
                    ai_result.get("severity"),
                    json.dumps(ai_result.get("rollback")),
                    json.dumps(ai_result.get("validation")),
                    json.dumps(ai_result.get("tokens_used", {})),
                ),
            )


def get_all_analyses(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM analyses ORDER BY id DESC LIMIT %s;",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def get_pr_analysis(pr_number: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM analyses WHERE pr_number = %s ORDER BY id DESC;",
                (pr_number,),
            )
            return [dict(row) for row in cur.fetchall()]
