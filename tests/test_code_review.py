# test_code_review.py – Test the code review function

import os
from dotenv import load_dotenv
load_dotenv()

from ai_agent_groq import generate_code_review

def test_code_review():
    print("=" * 60)
    print("🧪 Testing Code Review Function")
    print("=" * 60)
    
    # Sample diff with a bug
    diff = '''
def process_payment(amount, user):
    if not user:
        raise ValueError("User cannot be None")
    return user.balance - amount
'''
    
    changed_files = ["app.py"]
    services = ["payment_service"]
    
    print("📄 Sample diff:")
    print(diff)
    print("-" * 40)
    
    result = generate_code_review(diff, changed_files, services)
    
    print("\n🔍 Code Review Result:")
    print(f"   Code Quality: {result.get('code_quality')}")
    print(f"   Overall Verdict: {result.get('overall_verdict')}")
    print(f"   Bugs found: {len(result.get('bugs_found', []))}")
    if result.get('bugs_found'):
        for bug in result.get('bugs_found', []):
            print(f"      - {bug}")
    print(f"   Security issues: {len(result.get('security_issues', []))}")
    print(f"   Missing tests: {len(result.get('missing_tests', []))}")
    print(f"   Suggestions: {len(result.get('suggestions', []))}")
    
    print("\n" + "=" * 60)
    print("✅ Test completed!")

if __name__ == "__main__":
    test_code_review()