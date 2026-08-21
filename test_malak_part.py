# test_malak_part.py – Test for Malak's code

import os
from dotenv import load_dotenv

load_dotenv()

def test_imports():
    print("🧪 Testing imports...")
    from main import run_commit_analysis, calculate_blast_radius
    assert callable(run_commit_analysis)
    assert callable(calculate_blast_radius)
    from ai_agent_groq import generate_inline_suggestions
    assert callable(generate_inline_suggestions)
    from cache import get_cached_diff_suggestions, cache_diff_suggestions, get_cache_key_for_diff
    assert callable(get_cached_diff_suggestions)
    assert callable(cache_diff_suggestions)
    assert callable(get_cache_key_for_diff)
    print("✅ All imports work")

def test_bfs():
    print("🧪 Testing BFS...")
    from main import calculate_blast_radius
    result = calculate_blast_radius(["terraform/customer_database.tf"])
    assert result is not None
    assert len(result.get("affected_services", [])) > 0
    print(f"✅ BFS works: {result.get('changed_resource')} → {len(result.get('affected_services'))} services")

def test_cache():
    print("🧪 Testing cache...")
    from cache import get_cache_key_for_diff, get_cached_diff_suggestions, cache_diff_suggestions
    key = get_cache_key_for_diff("test")
    cache_diff_suggestions(key, [{"test": "data"}])
    cached = get_cached_diff_suggestions(key)
    assert cached is not None
    print("✅ Cache works")

def main():
    print("=" * 60)
    print("🧪 Testing Malak's Integration Parts")
    print("=" * 60)
    if not os.getenv("GITHUB_TOKEN"):
        print("❌ GITHUB_TOKEN not set in .env")
        return
    try:
        test_imports()
        test_bfs()
        test_cache()
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main()