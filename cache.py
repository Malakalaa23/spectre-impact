# cache.py – AI response caching for inline suggestions
# Location: C:\Users\Malak\spectre-impact\cache.py

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
import os

CACHE_DB = "cache.db"

def init_cache_db():
    """Initialize the cache database"""
    conn = sqlite3.connect(CACHE_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_cache (
            key TEXT PRIMARY KEY,
            response TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

def get_cache_key_for_diff(diff: str) -> str:
    """Generate a cache key for the entire diff"""
    return hashlib.md5(diff.encode()).hexdigest()

def get_cached_diff_suggestions(diff_key: str) -> list:
    """Get cached suggestions for a diff"""
    if not os.path.exists(CACHE_DB):
        return None
    
    conn = sqlite3.connect(CACHE_DB)
    row = conn.execute(
        "SELECT response, created_at FROM ai_cache WHERE key = ?", (f"diff_{diff_key}",)
    ).fetchone()
    conn.close()
    
    if row:
        created = datetime.fromisoformat(row[1])
        if datetime.now() - created < timedelta(hours=1):
            return json.loads(row[0])
    return None

def cache_diff_suggestions(diff_key: str, suggestions: list):
    """Cache suggestions for a diff"""
    conn = sqlite3.connect(CACHE_DB)
    conn.execute(
        "INSERT OR REPLACE INTO ai_cache (key, response, created_at) VALUES (?, ?, ?)",
        (f"diff_{diff_key}", json.dumps(suggestions), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

# Initialize on import
init_cache_db()