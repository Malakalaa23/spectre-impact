# test_full_flow.py – Full end-to-end integration test with mock diff
# Location: C:\Users\Malak\spectre-impact\test_full_flow.py

#!/usr/bin/env python3
"""
Full integration test – uses a mock diff with Terraform risk.
No PR needed – tests the full pipeline end-to-end.
"""

import os
from dotenv import load_dotenv

load_dotenv()

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

def test_full_flow():
    print("=" * 60)
    print("🚀 FULL END-TO-END TEST (Mock Diff)")
    print("=" * 60)
    
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN not set")
        return
    
    print(f"📄 Changed files: {CHANGED_FILES}")
    print("🚀 Running full commit analysis...")
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
        print("✅ Full pipeline completed!")
        print("💾 Check the database: sqlite3 history.db 'SELECT * FROM commit_analyses ORDER BY id DESC LIMIT 1;'")
        
    except Exception as e:
        print(f"❌ Full flow failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_full_flow()