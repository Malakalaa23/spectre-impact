"""
Test script to verify frontend + AI agent integration
Run with: python test_frontend_integration.py
"""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_ai_agent():
    """Test 1: Verify AI agent works."""
    print("="*60)
    print("Test 1: AI Agent")
    print("="*60)
    
    try:
        from ai_agent_groq import generate_insights
        
        result = generate_insights(["payment_service", "login_service"], 85)
        
        print(f"PASS: Severity:   {result['severity']}")
        print(f"PASS: Simulation: {result['simulation'][:80]}...")
        print(f"PASS: Rollback:   {len(result['rollback'])} commands")
        print(f"PASS: Validation: {len(result['validation'])} commands")
        
        if "tokens_used" in result:
            print(f"PASS: Tokens:     {result['tokens_used']['total_tokens']} total")
        
        return True
    except Exception as e:
        print(f"FAIL: AI Agent failed: {e}")
        return False

def test_paths():
    """Test 2: Verify paths and directories."""
    print("\n" + "="*60)
    print("Test 2: Directory Structure")
    print("="*60)
    
    # Check required directories
    required = ["dashboard", "dashboard/pages", "dashboard/data"]
    for dir_path in required:
        if os.path.exists(dir_path):
            print(f"PASS: {dir_path} exists")
        else:
            print(f"FAIL: {dir_path} missing")
    
    # Check required files
    required_files = [
        "ai_agent_groq.py",
        "dashboard/integration.py",
        "dashboard/style.py",
        "dashboard/data.py",
        "dashboard/app.py"
    ]
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"PASS: {file_path} exists")
        else:
            print(f"FAIL: {file_path} missing")

def test_integration_import():
    """Test 3: Verify integration can be imported."""
    print("\n" + "="*60)
    print("Test 3: Integration Import")
    print("="*60)
    
    try:
        # Add dashboard to path
        dashboard_path = os.path.join(os.path.dirname(__file__), 'dashboard')
        sys.path.append(dashboard_path)
        
        from integration import get_ai_analysis, get_pr_data, get_metrics
        
        # Test get_pr_data
        pr_data = get_pr_data(5)
        print(f"PASS: get_pr_data() returned {len(pr_data)} PRs")
        
        # Test get_metrics
        metrics = get_metrics()
        print(f"PASS: get_metrics() returned {metrics.get('total_prs', 0)} total PRs")
        
        # Test get_ai_analysis
        result = get_ai_analysis(["payment_service", "login_service"], 85)
        print(f"PASS: get_ai_analysis() returned severity: {result['severity']}")
        
        return True
    except Exception as e:
        print(f"FAIL: Integration failed: {e}")
        return False

def test_app_exists():
    """Test 4: Verify app.py exists."""
    print("\n" + "="*60)
    print("Test 4: Dashboard App")
    print("="*60)
    
    app_path = os.path.join(os.path.dirname(__file__), 'dashboard', 'app.py')
    
    if os.path.exists(app_path):
        print(f"PASS: dashboard/app.py exists")
        
        # Check file size
        size = os.path.getsize(app_path)
        print(f"PASS: File size: {size} bytes")
        
        return True
    else:
        print("FAIL: dashboard/app.py not found")
        return False

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("FRONTEND INTEGRATION TEST")
    print("="*60 + "\n")
    
    test_paths()
    test_ai_agent()
    test_integration_import()
    test_app_exists()
    
    print("\n" + "="*60)
    print("Tests Complete!")
    print("="*60)

if __name__ == "__main__":
    main()