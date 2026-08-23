#!/usr/bin/env python3
"""
Spectre Impact - Full System Test
Run with: python test_full_system.py

Tests:
1. Environment & Configuration
2. Database
3. BFS Engine (Blast Radius)
4. AI Agent
5. BFS + AI Integration
6. Multi-Level Summaries
7. Caching
8. Diff Parser
9. GitHub Client (optional - requires token)
10. Dashboard Files
11. Webhook Parser
12. Main Imports
"""

import sys
import os
import json
import traceback
from pathlib import Path

# ============================================================
# Helper Functions
# ============================================================

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 60)
    print(f"🧪 {title}")
    print("=" * 60)

def print_result(passed, message, details=""):
    """Print a test result"""
    status = "✅" if passed else "❌"
    print(f"{status} {message}")
    if details:
        print(f"   {details}")

def check_file_exists(filepath):
    """Check if a file exists"""
    return os.path.exists(filepath)

# ============================================================
# TEST 1: Environment & Configuration
# ============================================================

def test_environment():
    """Test Python version, dependencies, and environment variables"""
    print_section("Test 1: Environment & Configuration")
    all_passed = True

    # Python version
    py_version = sys.version_info
    passed = py_version.major >= 3 and py_version.minor >= 8
    print_result(passed, f"Python {py_version.major}.{py_version.minor}.{py_version.micro}", 
                 "✅" if passed else "Python 3.8+ required")

    # Check .env file
    passed = check_file_exists(".env")
    print_result(passed, ".env file exists")

    # Check GROQ_API_KEY
    try:
        from dotenv import load_dotenv
        load_dotenv()
        groq_key = os.getenv("GROQ_API_KEY")
        passed = groq_key is not None and groq_key.startswith("gsk_")
        print_result(passed, "GROQ_API_KEY configured", 
                     f"Found: {groq_key[:10]}..." if passed else "Missing or invalid")
    except Exception as e:
        print_result(False, f"GROQ_API_KEY check failed: {e}")
        all_passed = False

    # Check GITHUB_TOKEN
    try:
        github_token = os.getenv("GITHUB_TOKEN")
        passed = github_token is not None and github_token.startswith("ghp_")
        print_result(passed, "GITHUB_TOKEN configured",
                     f"Found: {github_token[:10]}..." if passed else "Missing or invalid")
    except Exception as e:
        print_result(False, f"GITHUB_TOKEN check failed: {e}")
        all_passed = False

    return all_passed

# ============================================================
# TEST 2: Database
# ============================================================

def test_database():
    """Test database initialization and operations"""
    print_section("Test 2: Database")
    all_passed = True

    try:
        from database import init_db, get_all_analyses, save_analysis, init_commit_table
        
        # Initialize database
        init_db()
        init_commit_table()
        print_result(True, "Database initialized")

        # Check if tables exist
        import sqlite3
        conn = sqlite3.connect("history.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_tables = ["analyses", "commit_analyses"]
        for table in expected_tables:
            passed = table in tables
            print_result(passed, f"Table '{table}' exists")
            if not passed:
                all_passed = False

        # Test save and retrieve
        test_pr = 9999
        test_bfs = {"changed_resource": "test", "affected_services": ["test"], "business_impact": 50}
        test_ai = {"simulation": "test", "severity": "Medium", "rollback": ["test"], "validation": ["test"], "tokens_used": {}}
        
        try:
            save_analysis(test_pr, "test/repo", test_bfs, test_ai)
            results = get_all_analyses(limit=1)
            passed = len(results) > 0
            print_result(passed, "Save and retrieve analysis works")
        except Exception as e:
            print_result(False, f"Save/retrieve failed: {e}")
            all_passed = False

    except Exception as e:
        print_result(False, f"Database test failed: {e}")
        return False

    return all_passed

# ============================================================
# TEST 3: BFS Engine (Blast Radius)
# ============================================================

def test_bfs():
    """Test the BFS engine with sample data"""
    print_section("Test 3: BFS Engine (Blast Radius)")
    all_passed = True

    try:
        from main import calculate_blast_radius

        # Test with a known file
        test_files = ["terraform/customer_database.tf"]
        result = calculate_blast_radius(test_files)

        # Check required fields
        required_fields = ["changed_resource", "affected_services", "business_impact"]
        for field in required_fields:
            passed = field in result
            print_result(passed, f"BFS result contains '{field}'")
            if not passed:
                all_passed = False

        print_result(True, f"Changed resource: {result.get('changed_resource', 'unknown')}")
        print_result(True, f"Affected services: {len(result.get('affected_services', []))} services")
        print_result(True, f"Business impact: {result.get('business_impact', 0)}%")

        # Test with empty list
        empty_result = calculate_blast_radius([])
        passed = empty_result.get("changed_resource") == "unknown"
        print_result(passed, "Handles empty file list gracefully")

    except Exception as e:
        print_result(False, f"BFS test failed: {e}")
        traceback.print_exc()
        return False

    return all_passed

# ============================================================
# TEST 4: AI Agent
# ============================================================

def test_ai_agent():
    """Test the AI agent"""
    print_section("Test 4: AI Agent")
    all_passed = True

    try:
        from ai_agent_groq import generate_insights

        # Test AI with sample data
        result = generate_insights(["payment_service", "login_service"], 85)

        # Check required fields
        required_fields = ["simulation", "severity", "rollback", "validation", "tokens_used"]
        for field in required_fields:
            passed = field in result
            print_result(passed, f"AI result contains '{field}'")
            if not passed:
                all_passed = False

        # Check severity is valid
        severity = result.get("severity", "")
        valid_severities = ["Low", "Medium", "High", "Critical"]
        passed = severity in valid_severities
        print_result(passed, f"AI severity: {severity}")

        # Check simulation is not empty
        simulation = result.get("simulation", "")
        passed = len(simulation) > 10
        print_result(passed, f"AI simulation: {simulation[:60]}..." if passed else "Simulation is empty")

        # Check rollback has steps
        rollback = result.get("rollback", [])
        passed = len(rollback) > 0
        print_result(passed, f"AI rollback: {len(rollback)} steps")

        # Check validation has steps
        validation = result.get("validation", [])
        passed = len(validation) > 0
        print_result(passed, f"AI validation: {len(validation)} steps")

        # Check tokens
        tokens = result.get("tokens_used", {})
        total_tokens = tokens.get("total_tokens", 0)
        passed = total_tokens > 0
        print_result(passed, f"AI tokens: {total_tokens}")

    except Exception as e:
        print_result(False, f"AI Agent test failed: {e}")
        traceback.print_exc()
        return False

    return all_passed

# ============================================================
# TEST 5: BFS + AI Integration
# ============================================================

def test_integration():
    """Test that BFS and AI work together"""
    print_section("Test 5: BFS + AI Integration")
    all_passed = True

    try:
        from main import calculate_blast_radius
        from ai_agent_groq import generate_insights

        # Step 1: BFS
        changed_files = ["terraform/customer_database.tf"]
        bfs_result = calculate_blast_radius(changed_files)

        print_result(True, f"BFS found {len(bfs_result.get('affected_services', []))} services")

        # Step 2: AI
        services = bfs_result.get("affected_services", [])
        impact = bfs_result.get("business_impact", 0)
        ai_result = generate_insights(services, impact)

        print_result(True, f"AI generated {ai_result.get('severity', 'Unknown')} severity")
        print_result(True, f"AI simulation: {ai_result.get('simulation', '')[ :60]}...")

        # Verify they work together
        passed = len(services) > 0 and ai_result.get("severity") is not None
        print_result(passed, "BFS + AI integration works")

    except Exception as e:
        print_result(False, f"Integration test failed: {e}")
        traceback.print_exc()
        return False

    return all_passed

# ============================================================
# TEST 6: Multi-Level Summaries
# ============================================================

def test_summaries():
    """Test multi-level summaries"""
    print_section("Test 6: Multi-Level Summaries")
    all_passed = True

    try:
        from ai_agent_groq import generate_insights
        from multi_level_summary import generate_full_report

        # Generate AI insights first
        ai_result = generate_insights(["payment_service", "login_service"], 80)

        # ✅ FIXED: Pass both required arguments
        report = generate_full_report(ai_result, 80)
        
        # Check report structure
        passed = "devops" in report and "executive" in report
        print_result(passed, "Multi-level summaries generated")

        if passed:
            print_result(True, f"DevOps view: {len(report.get('devops', ''))} characters")
            print_result(True, f"Executive view: {len(report.get('executive', ''))} characters")

    except ImportError as e:
        print_result(False, f"multi_level_summary.py not found: {e}")
        all_passed = False
    except TypeError as e:
        print_result(False, f"generate_full_report() signature mismatch: {e}")
        print_result(False, "Expected: generate_full_report(ai_result, impact_percentage)")
        all_passed = False
    except Exception as e:
        print_result(False, f"Summaries test failed: {e}")
        traceback.print_exc()
        return False

    return all_passed

# ============================================================
# TEST 7: Caching
# ============================================================

def test_cache():
    """Test the caching system"""
    print_section("Test 7: Caching")
    all_passed = True

    try:
        from cache import get_cache_key_for_diff, cache_diff_suggestions, get_cached_diff_suggestions

        # Test cache operations
        test_key = "test_key_123"
        test_data = [{"file": "test.py", "line": 10, "suggestion": "Test suggestion"}]

        # Save to cache
        cache_diff_suggestions(test_key, test_data)
        print_result(True, "Cache save works")

        # Retrieve from cache
        cached = get_cached_diff_suggestions(test_key)
        passed = cached is not None and len(cached) > 0
        print_result(passed, "Cache retrieve works")

        # Check key generation
        key1 = get_cache_key_for_diff("test diff content")
        key2 = get_cache_key_for_diff("test diff content")
        passed = key1 == key2 and len(key1) > 0
        print_result(passed, "Cache key generation is consistent")

    except Exception as e:
        print_result(False, f"Cache test failed: {e}")
        traceback.print_exc()
        return False

    return all_passed

# ============================================================
# TEST 8: Diff Parser
# ============================================================

def test_diff_parser():
    """Test the diff parser"""
    print_section("Test 8: Diff Parser")
    all_passed = True

    try:
        from diff_parser import parse_unified_diff

        test_diff = """diff --git a/app.py b/app.py
@@ -10,6 +10,8 @@ def hello():
     print("Hello")
+    print("World")
+    return True
     print("Goodbye")"""

        result = parse_unified_diff(test_diff)

        # Check that it parsed correctly
        passed = "app.py" in result
        print_result(passed, "Diff parser found file")

        if passed:
            added_lines = result["app.py"].get("added_lines", [])
            passed = len(added_lines) == 2
            print_result(passed, f"Diff parser found {len(added_lines)} added lines")

        # Test with empty diff
        empty_result = parse_unified_diff("")
        passed = isinstance(empty_result, dict)
        print_result(passed, "Diff parser handles empty input")

    except Exception as e:
        print_result(False, f"Diff parser test failed: {e}")
        traceback.print_exc()
        return False

    return all_passed

# ============================================================
# TEST 9: GitHub Client (Optional)
# ============================================================

def test_github_client():
    """Test GitHub client functions (optional - requires token)"""
    print_section("Test 9: GitHub Client (Optional)")
    all_passed = True

    try:
        from github_client import fetch_commit_diff, get_pr_for_branch
        from dotenv import load_dotenv
        import os

        load_dotenv()
        token = os.getenv("GITHUB_TOKEN")

        if not token:
            print_result(False, "GITHUB_TOKEN not set - skipping GitHub tests")
            return True  # Not a failure, just skipped

        # Test diff fetch
        try:
            diff = fetch_commit_diff("Malakalaa23/spectre-impact", "c2933ba")
            passed = len(diff) > 0
            print_result(passed, f"Commit diff fetched: {len(diff)} characters")
        except Exception as e:
            print_result(False, f"Diff fetch failed: {e}")

        # Test PR detection
        try:
            pr_num = get_pr_for_branch("Malakalaa23/spectre-test", "main")
            print_result(True, f"PR detection works: {pr_num}")
        except Exception as e:
            print_result(False, f"PR detection failed: {e}")

    except ImportError as e:
        print_result(False, f"GitHub client import failed: {e}")
        return False
    except Exception as e:
        print_result(False, f"GitHub client test failed: {e}")
        return False

    return all_passed

# ============================================================
# TEST 10: Dashboard Files
# ============================================================

def test_dashboard():
    """Test dashboard files exist"""
    print_section("Test 10: Dashboard")
    all_passed = True

    try:
        dashboard_dir = Path("dashboard")
        if not dashboard_dir.exists():
            print_result(False, "dashboard directory does not exist")
            return False

        # Check main files
        main_files = ["app.py", "style.py", "data.py"]
        for file in main_files:
            passed = (dashboard_dir / file).exists()
            print_result(passed, f"dashboard/{file} exists")
            if not passed:
                all_passed = False

        # Check pages
        pages_dir = dashboard_dir / "pages"
        if pages_dir.exists():
            page_files = ["PR_Analysis.py", "Analytics.py", "Weekly_Review.py", 
                         "Business_View.py", "How_It_Works.py", "About.py"]
            for file in page_files:
                passed = (pages_dir / file).exists()
                print_result(passed, f"dashboard/pages/{file} exists")
                if not passed:
                    all_passed = False
        else:
            print_result(False, "dashboard/pages directory does not exist")
            all_passed = False

    except Exception as e:
        print_result(False, f"Dashboard test failed: {e}")
        return False

    return all_passed

# ============================================================
# TEST 11: Webhook Parser
# ============================================================

def test_webhook_parser():
    """Test the webhook payload parser"""
    print_section("Test 11: Webhook Parser")
    all_passed = True

    try:
        from main import parse_payload

        test_payload = {
            "action": "opened",
            "pull_request": {"number": 42},
            "repository": {"full_name": "test/repo"}
        }

        pr_number, repo_name, action = parse_payload(test_payload)

        passed = pr_number == 42
        print_result(passed, f"Parsed PR number: {pr_number}")

        passed = repo_name == "test/repo"
        print_result(passed, f"Parsed repo name: {repo_name}")

        passed = action == "opened"
        print_result(passed, f"Parsed action: {action}")

        # ✅ FIXED: Test with invalid payload using try/except
        try:
            parse_payload({})
            print_result(False, "Should handle invalid payload")
        except (AttributeError, TypeError, KeyError):
            print_result(True, "Handles invalid payload gracefully")

    except Exception as e:
        print_result(False, f"Webhook parser test failed: {e}")
        return False

    return all_passed

# ============================================================
# TEST 12: Main Imports
# ============================================================

def test_imports():
    """Test all main imports work"""
    print_section("Test 12: Main Imports")
    all_passed = True

    modules = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "uvicorn"),
        ("github", "Github"),
        ("groq", "Groq"),
        ("yaml", "yaml"),
        ("streamlit", "streamlit"),
    ]

    for module_name, import_name in modules:
        try:
            exec(f"import {module_name}")
            print_result(True, f"Import: {module_name}")
        except ImportError as e:
            print_result(False, f"Import: {module_name} - {e}")
            all_passed = False

    # Check main imports
    try:
        from main import app, run_analysis_pipeline, run_commit_analysis
        print_result(True, "Main app imports work")
    except Exception as e:
        print_result(False, f"Main imports failed: {e}")
        all_passed = False

    return all_passed

# ============================================================
# MAIN
# ============================================================

def main():
    """Run all tests and print summary"""
    print("\n" + "=" * 60)
    print("🚀 SPECTRE IMPACT - FULL SYSTEM TEST")
    print("=" * 60)

    tests = [
        ("Environment & Configuration", test_environment),
        ("Database", test_database),
        ("BFS Engine (Blast Radius)", test_bfs),
        ("AI Agent", test_ai_agent),
        ("BFS + AI Integration", test_integration),
        ("Multi-Level Summaries", test_summaries),
        ("Caching", test_cache),
        ("Diff Parser", test_diff_parser),
        ("GitHub Client", test_github_client),
        ("Dashboard", test_dashboard),
        ("Webhook Parser", test_webhook_parser),
        ("Main Imports", test_imports),
    ]

    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ {name} crashed: {e}")
            traceback.print_exc()
            results[name] = False

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    for name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {name}")

    print("=" * 60)
    print(f"🎯 {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED! YOUR SYSTEM IS READY!")
    else:
        print(f"\n⚠️ {total_count - passed_count} tests failed. Please check the output above.")

    return passed_count == total_count

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)