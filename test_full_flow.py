# test_full_flow.py – Full end-to-end integration test with mock diff
# Location: C:\Users\Malak\spectre-impact\test_full_flow.py

#!/usr/bin/env python3
"""
Full integration test for Spectre Impact.

Contains two test suites:
    1. Pipeline test — runs the full commit analysis with a mock diff.
    2. Memory integration test — verifies Lya's session tracking works
       end-to-end (mood signals, incidents, cross-turn state).

Run everything:
    python test_full_flow.py

Run one suite:
    python test_full_flow.py pipeline
    python test_full_flow.py memory
"""

import asyncio
import io
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# ===========================================================================
# Shared test fixtures
# ===========================================================================
TEST_DIFF = """
diff --git a/terraform/risky_db.tf b/terraform/risky_db.tf
@@ -1,3 +1,9 @@
 resource "aws_db_instance" "risky_db" {
+  engine         = "postgres"
+  instance_class = "db.t3.medium"
+  name           = "production_db"
+  username       = "db_admin"
+  password       = "SuperSecret123!"
+  publicly_accessible = true
+  backup_retention_period = 0
 }
"""

CHANGED_FILES = ["terraform/risky_db.tf"]
REPO_NAME = "Malakalaa23/spectre-impact"
COMMIT_SHA = "test_commit"


# ===========================================================================
# TEST 1 — Pipeline (commit analysis end-to-end)
# ===========================================================================
def test_pipeline() -> None:
    print("=" * 60)
    print("PIPELINE TEST (Mock Diff)")
    print("=" * 60)

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN not set — skipping pipeline test")
        return

    print(f"Changed files: {CHANGED_FILES}")
    print("Running full commit analysis...")
    print("-" * 40)

    try:
        import github_client

        original_fetch = github_client.fetch_commit_diff

        def mock_fetch_diff(repo_name, commit_sha):
            return TEST_DIFF

        github_client.fetch_commit_diff = mock_fetch_diff

        from main import run_commit_analysis

        run_commit_analysis(REPO_NAME, COMMIT_SHA, "main", CHANGED_FILES)

        github_client.fetch_commit_diff = original_fetch

        print("-" * 40)
        print("Full pipeline completed.")
        print("Check the database: sqlite3 history.db 'SELECT * FROM commit_analyses ORDER BY id DESC LIMIT 1;'")

    except Exception as e:
        print(f"Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()


# ===========================================================================
# TEST 2 — Memory integration (session context end-to-end)
# ===========================================================================
async def _memory_test_async() -> None:
    from chat.agent import chat
    from chat.memory import clear_user, get_session_context

    user_id = "user-memory-test"
    session_id = "sess-memory-test"

    clear_user(user_id)

    print("=" * 60)
    print("MEMORY INTEGRATION TEST")
    print("=" * 60)

    # --- Turn 1: neutral greeting ---
    print()
    print("--- Turn 1: neutral greeting ---")
    r1 = await chat("Hey Lya, how's it going?", session_id, user_id=user_id)
    print(f"  Lya: {r1['response'][:150]}")
    ctx = get_session_context(user_id)
    print(f"  session_count: {ctx.get('session_count')}")
    print(f"  turn_count:    {ctx.get('turn_count')}")
    print(f"  mood:          {ctx.get('mood')}")

    # --- Turn 2: mention a service ---
    print()
    print("--- Turn 2: mention payment_service ---")
    r2 = await chat("Tell me about payment_service.", session_id, user_id=user_id)
    print(f"  Lya: {r2['response'][:150]}")
    ctx = get_session_context(user_id)
    print(f"  turn_count:    {ctx.get('turn_count')}")
    print(f"  incidents:     {[i['service'] for i in ctx.get('recent_incidents', [])]}")

    # --- Turn 3: venting (mood signals) ---
    print()
    print("--- Turn 3: venting + ALL CAPS ---")
    r3 = await chat(
        "UGH I HAVE BEEN DEBUGGING ALL DAY!!! I am so done with this.",
        session_id,
        user_id=user_id,
    )
    print(f"  Lya: {r3['response'][:150]}")
    ctx = get_session_context(user_id)
    print(f"  turn_count:    {ctx.get('turn_count')}")
    print(f"  mood:          {ctx.get('mood')}")
    print(f"  mood_signals:  {ctx.get('mood_signals')}")

    # --- Final summary ---
    print()
    print("=" * 60)
    print("FINAL SESSION CONTEXT")
    print("=" * 60)
    print(f"  session_count:  {ctx.get('session_count')}")
    print(f"  turn_count:     {ctx.get('turn_count')}")
    print(f"  mood:           {ctx.get('mood')}")
    print(f"  signals:        {ctx.get('mood_signals')}")
    print(f"  incidents:      {[i['service'] for i in ctx.get('recent_incidents', [])]}")

    # --- Assertions ---
    print()
    print("--- Assertions ---")
    failures = []

    if ctx.get("session_count") != 1:
        failures.append(f"expected session_count=1, got {ctx.get('session_count')}")
    if ctx.get("turn_count") != 3:
        failures.append(f"expected turn_count=3, got {ctx.get('turn_count')}")
    if ctx.get("mood") not in ("stressed", "frustrated"):
        failures.append(f"expected mood in (stressed, frustrated), got {ctx.get('mood')}")

    signals = ctx.get("mood_signals") or []
    if "all_caps" not in signals:
        failures.append("expected all_caps signal, not found")
    if "exclamations" not in signals:
        failures.append("expected exclamations signal, not found")
    if "vent" not in signals:
        failures.append("expected vent signal, not found")

    incidents = [i["service"] for i in ctx.get("recent_incidents", [])]
    if "payment_service" not in incidents:
        failures.append("expected payment_service in incidents, not found")

    if failures:
        print("  FAILED:")
        for f in failures:
            print(f"    - {f}")
    else:
        print("  All assertions passed.")


def test_memory() -> None:
    try:
        asyncio.run(_memory_test_async())
    except Exception as e:
        print(f"Memory integration test failed: {e}")
        import traceback
        traceback.print_exc()


# ===========================================================================
# Main
# ===========================================================================
def main() -> None:
    args = sys.argv[1:]

    if not args or "all" in args:
        test_pipeline()
        print()
        print()
        test_memory()
        return

    if "pipeline" in args:
        test_pipeline()
    if "memory" in args:
        test_memory()


if __name__ == "__main__":
    main()