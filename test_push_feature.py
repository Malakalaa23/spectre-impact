#!/usr/bin/env python3
"""
Test the push-event feature: diff parsing, PR lookup, diff fetch, and DB functions.
Does not require a real webhook call.
"""

import os
import sqlite3
from dotenv import load_dotenv

from diff_parser import parse_unified_diff
from github_client import get_pr_for_branch, fetch_commit_diff
import database

load_dotenv()

SAMPLE_DIFF = """diff --git a/app.py b/app.py
index e69de29..4b825dc 100644
--- a/app.py
+++ b/app.py
@@ -10,6 +10,8 @@ def handler():
     existing_line = 1
     another_line = 2
+    new_line_a = 3
+    new_line_b = 4
     trailing_line = 5
"""

REPO_NAME = "Malakalaa23/spectre-test"
BRANCH = "main"
TEST_COMMIT_SHA = "test-commit-1234567890"


def test_diff_parser():
    print("🧪 Testing parse_unified_diff...")
    result = parse_unified_diff(SAMPLE_DIFF)
    assert "app.py" in result, "Expected app.py in parsed diff result"
    assert len(result["app.py"]["added_lines"]) == 2, f"Expected 2 added lines, got {result['app.py']}"
    print(f"✅ parse_unified_diff OK: {result}")


def test_pr_lookup():
    print("🧪 Testing get_pr_for_branch (requires GITHUB_TOKEN + real repo)...")
    if not os.getenv("GITHUB_TOKEN"):
        print("⚠️  GITHUB_TOKEN not set – skipping live PR lookup.")
        return
    pr_number = get_pr_for_branch(REPO_NAME, BRANCH)
    print(f"✅ get_pr_for_branch returned: {pr_number}")


def test_diff_fetch():
    print("🧪 Testing fetch_commit_diff (requires GITHUB_TOKEN + real repo/commit)...")
    if not os.getenv("GITHUB_TOKEN"):
        print("⚠️  GITHUB_TOKEN not set – skipping live diff fetch.")
        return
    diff = fetch_commit_diff(REPO_NAME, "HEAD")
    print(f"✅ fetch_commit_diff returned {len(diff)} chars")


def test_commit_analysis_db():
    print("🧪 Testing commit_analyses DB functions...")
    assert not database.is_commit_analyzed(TEST_COMMIT_SHA), "Test commit should not be analyzed yet"

    bfs_result = {"affected_services": ["checkout-service"], "business_impact": 42}
    database.save_commit_analysis(
        TEST_COMMIT_SHA, REPO_NAME, BRANCH,
        ["app.py"], bfs_result, ["Add tests for new_line_a"]
    )

    assert database.is_commit_analyzed(TEST_COMMIT_SHA), "Commit should be marked analyzed after save"
    rows = database.get_commit_analysis(TEST_COMMIT_SHA)
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
    assert rows[0]["affected_services"] == ["checkout-service"]
    print(f"✅ commit_analyses round-trip OK: {rows[0]}")

    # Clean up the test row so repeated runs stay idempotent.
    conn = sqlite3.connect(database.DB_FILE)
    conn.execute("DELETE FROM commit_analyses WHERE commit_sha = ?", (TEST_COMMIT_SHA,))
    conn.commit()
    conn.close()


def main():
    test_diff_parser()
    test_pr_lookup()
    test_diff_fetch()
    test_commit_analysis_db()
    print("✅ All push feature tests completed!")


if __name__ == "__main__":
    main()
