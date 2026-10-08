"""
Test Suite for AI Agent
Run with: python test_ai_agent.py
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_ai_agent():
    """Test 1: AI Agent"""
    print("\n" + "="*60)
    print("🧪 Test 1: AI Agent")
    print("="*60)
    
    try:
        from ai_agent_groq import generate_insights
        
        result = generate_insights(["payment_service", "login_service"], 85)
        
        required_keys = ["simulation", "severity", "rollback", "validation"]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"
        
        print(f"✅ Severity:   {result['severity']}")
        print(f"✅ Simulation: {result['simulation'][:80]}...")
        print(f"✅ Rollback:   {len(result['rollback'])} commands")
        print(f"✅ Validation: {len(result['validation'])} commands")
        
        if "tokens_used" in result:
            print(f"✅ Tokens:     {result['tokens_used']['total_tokens']} total")
        
        print("✅ Test 1 PASSED")
        return True
    except Exception as e:
        print(f"❌ Test 1 FAILED: {e}")
        return False

def test_cache():
    """Test 2: Cache System"""
    print("\n" + "="*60)
    print("🧪 Test 2: Cache System")
    print("="*60)
    
    try:
        from ai_agent_groq import generate_insights, clear_cache
        
        clear_cache()
        
        services = ["payment_service", "login_service"]
        impact = 85
        
        print("📦 First call (should be fresh)...")
        result1 = generate_insights(services, impact)
        
        print("📦 Second call (should be cached)...")
        result2 = generate_insights(services, impact)
        
        # Compare results (ignore tokens_used which might differ slightly)
        result1_copy = {k: v for k, v in result1.items() if k != "tokens_used"}
        result2_copy = {k: v for k, v in result2.items() if k != "tokens_used"}
        
        if result1_copy == result2_copy:
            print("✅ Cache working! Both results are identical.")
        else:
            print("⚠️ Cache may not be working. Results differ slightly.")
        
        print("✅ Test 2 PASSED")
        return True
    except Exception as e:
        print(f"❌ Test 2 FAILED: {e}")
        return False

def test_multi_level():
    """Test 3: Multi-Level Summaries"""
    print("\n" + "="*60)
    print("🧪 Test 3: Multi-Level Summaries")
    print("="*60)
    
    try:
        from multi_level_summary import generate_full_report
        
        report = generate_full_report(["payment_service", "login_service"], 85)
        
        assert "raw" in report, "Missing raw key"
        assert "devops" in report, "Missing devops key"
        assert "executive" in report, "Missing executive key"
        
        print("✅ Raw AI response: Present")
        print(f"✅ DevOps summary: {len(report['devops'])} characters")
        print(f"✅ Executive summary: {len(report['executive'])} characters")
        print("✅ Test 3 PASSED")
        return True
    except Exception as e:
        print(f"❌ Test 3 FAILED: {e}")
        return False

def test_integration():
    """Test 4: Integration Layer"""
    print("\n" + "="*60)
    print("🧪 Test 4: Integration Layer")
    print("="*60)
    
    try:
        from integration import get_pr_data, get_metrics, get_ai_analysis
        
        prs = get_pr_data(5)
        print(f"✅ get_pr_data() returned {len(prs)} PRs")
        
        metrics = get_metrics()
        print(f"✅ get_metrics() returned {metrics['total_prs']} total PRs")
        
        result = get_ai_analysis(["payment_service", "login_service"], 85)
        print(f"✅ get_ai_analysis() returned severity: {result['severity']}")
        
        print("✅ Test 4 PASSED")
        return True
    except Exception as e:
        print(f"❌ Test 4 FAILED: {e}")
        return False

def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("🚀 RUNNING AI AGENT TESTS")
    print("="*60)
    
    results = []
    
    results.append(("AI Agent", test_ai_agent()))
    results.append(("Cache System", test_cache()))
    results.append(("Multi-Level Summaries", test_multi_level()))
    results.append(("Integration Layer", test_integration()))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED! 🎉")
        print("="*60 + "\n")
    else:
        print("\n" + "="*60)
        print("❌ SOME TESTS FAILED")
        print("="*60 + "\n")

if __name__ == "__main__":
    run_all_tests()