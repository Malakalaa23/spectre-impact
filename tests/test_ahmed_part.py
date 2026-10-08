# test_ahmed_part.py – Test Ahmed's code
# Location: C:\Users\Malak\spectre-impact\test_ahmed_part.py

import os
from dotenv import load_dotenv
from diff_parser import parse_unified_diff
from github_client import fetch_commit_diff, get_pr_for_branch

load_dotenv()

def test_diff_parser():
    print("🧪 Testing diff parser...")
    test_diff = """
diff --git a/app.py b/app.py
@@ -10,6 +10,8 @@ def hello():
     print("Hello")
+    print("World")
+    return True
     print("Goodbye")
"""
    result = parse_unified_diff(test_diff)
    assert "app.py" in result, "File not found"
    assert len(result["app.py"]["added_lines"]) == 2, "Incorrect line count"
    print("✅ Diff parser works")

def test_diff_fetch():
    print("🧪 Testing diff fetch...")
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("⚠️ GITHUB_TOKEN not set – skipping")
        return
    diff = fetch_commit_diff("Malakalaa23/spectre-test", "cfa39cd")
    assert len(diff) > 0, "Diff is empty"
    print(f"✅ Diff fetch works: {len(diff)} chars")

def main():
    print("=" * 60)
    print("🧪 Testing Ahmed's Parts")
    print("=" * 60)
    
    test_diff_parser()
    test_diff_fetch()
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    main()