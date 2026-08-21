#!/usr/bin/env python3
import requests
import json
import sqlite3
import time
import os

WEBHOOK_URL = "http://localhost:8000/webhook"
DB_PATH = "history.db"

payload = {
    "action": "opened",
    "pull_request": {"number": 999, "title": "Test PR", "head": {"sha": "fake"}},
    "repository": {"full_name": "test/repo"},
    "changed_files": ["terraform/customer_database.tf"]   # not used anymore, but kept for compatibility
}

def main():
    print("🚀 Sending test webhook...")
    resp = requests.post(WEBHOOK_URL, json=payload)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")

    time.sleep(5)   # give pipeline time to run

    if not os.path.exists(DB_PATH):
        print("❌ Database file not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Check if table exists – CORRECT TABLE NAME: analyses
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analyses'")
    if not cursor.fetchone():
        print("❌ Table 'analyses' does not exist – database not initialized properly.")
        conn.close()
        return

    cursor.execute("SELECT * FROM analyses ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        print("✅ New DB entry found!")
        print(row)
        # Print column names for clarity
        print("Columns:", [desc[0] for desc in cursor.description] if cursor.description else [])
    else:
        print("❌ No new entry – pipeline may have failed. Check webhook.log for errors.")

if __name__ == "__main__":
    main()