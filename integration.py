"""
Integration Layer for Spectre Impact
Connects AI agent to frontend and backend
"""

import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_agent_groq import generate_insights, clear_cache, get_cache_size

# ------------------------------
# CONSTANTS
# ------------------------------
SEVERITY_MAP = {
    "Critical": {"label": "CRITICAL", "emoji": "🚨", "color": "#dc3545"},
    "High": {"label": "HIGH", "emoji": "🔴", "color": "#fd7e14"},
    "Medium": {"label": "MEDIUM", "emoji": "🟡", "color": "#ffc107"},
    "Low": {"label": "LOW", "emoji": "🟢", "color": "#28a745"},
    "Unknown": {"label": "UNKNOWN", "emoji": "⚪", "color": "#6c757d"}
}

SEVERITY_MAPPING = {
    "Critical": "HIGH",
    "High": "HIGH",
    "Medium": "MEDIUM",
    "Low": "LOW"
}

DEFAULT_PR_DETAILS = {
    "repository": "Unknown",
    "severity": "MEDIUM",
    "impact": 50,
    "summary": "No details available for this PR.",
    "changed_files": ["Unknown"],
    "services": ["Unknown"],
    "simulation": ["No simulation available"],
    "rollback": ["Rollback not available"],
    "validation": ["Validation not available"]
}

# ------------------------------
# MOCK DATA (For testing without backend)
# ------------------------------
def get_mock_pr_data() -> List[Dict]:
    """Generate mock PR data for testing the dashboard."""
    now = datetime.now()
    
    return [
        {
            "id": 1,
            "pr": "#445",
            "repository": "Spectre",
            "severity": "HIGH",
            "impact": 80,
            "date": now.strftime("%b %d, %Y"),
            "details": {
                "id": 1,
                "pr_number": 445,
                "repo_name": "Spectre",
                "changed_resource": "database.tf",
                "affected_services": ["Login Service", "Payment Gateway", "Main Database"],
                "business_impact": 80,
                "simulation": "Database migration fails → Login service loses connection → Checkout requests timeout → Customers cannot purchase",
                "severity": "Critical",
                "rollback": ["Revert the database migration", "Restart the login service", "Verify database connectivity"],
                "validation": ["curl -f /health", "kubectl get pods", "kubectl logs --tail=50"],
                "created_at": now.strftime("%Y-%m-%d %H:%M:%S")
            }
        },
        {
            "id": 2,
            "pr": "#443",
            "repository": "Spectre",
            "severity": "HIGH",
            "impact": 75,
            "date": (now - timedelta(days=1)).strftime("%b %d, %Y"),
            "details": {
                "id": 2,
                "pr_number": 443,
                "repo_name": "Spectre",
                "changed_resource": "auth_middleware.py",
                "affected_services": ["Login Service", "Authentication", "API Gateway"],
                "business_impact": 75,
                "simulation": "Auth middleware deploys → Session tokens fail validation → Users get logged out unexpectedly → Support tickets spike",
                "severity": "High",
                "rollback": ["Revert the auth middleware change", "Invalidate and reissue affected sessions", "Confirm login success rate returns to normal"],
                "validation": ["curl -f /auth/health", "kubectl logs -l app=auth", "kubectl get pods"],
                "created_at": (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            }
        },
        {
            "id": 3,
            "pr": "#442",
            "repository": "Spectre",
            "severity": "MEDIUM",
            "impact": 45,
            "date": (now - timedelta(days=2)).strftime("%b %d, %Y"),
            "details": {
                "id": 3,
                "pr_number": 442,
                "repo_name": "Spectre",
                "changed_resource": "gateway_config.yaml",
                "affected_services": ["API Gateway", "Authentication"],
                "business_impact": 45,
                "simulation": "New rate limits deploy → Peak-hour traffic approaches the new threshold → Some legitimate requests get throttled",
                "severity": "Medium",
                "rollback": ["Revert rate-limit thresholds to previous values", "Monitor gateway error rate for 15 minutes"],
                "validation": ["curl -f /gateway/health", "kubectl logs -l app=gateway", "kubectl get pods"],
                "created_at": (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
            }
        },
        {
            "id": 4,
            "pr": "#441",
            "repository": "Auth-Gateway",
            "severity": "LOW",
            "impact": 15,
            "date": (now - timedelta(days=3)).strftime("%b %d, %Y"),
            "details": {
                "id": 4,
                "pr_number": 441,
                "repo_name": "Auth-Gateway",
                "changed_resource": "logging_config.py",
                "affected_services": ["Authentication"],
                "business_impact": 15,
                "simulation": "Logging change deploys → Log verbosity increases slightly → No impact on request handling",
                "severity": "Low",
                "rollback": ["Revert the logging configuration"],
                "validation": ["curl -f /auth/health", "kubectl logs -l app=auth", "kubectl get pods"],
                "created_at": (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
            }
        },
        {
            "id": 5,
            "pr": "#440",
            "repository": "Payment-Service",
            "severity": "MEDIUM",
            "impact": 40,
            "date": (now - timedelta(days=4)).strftime("%b %d, %Y"),
            "details": {
                "id": 5,
                "pr_number": 440,
                "repo_name": "Payment-Service",
                "changed_resource": "retry_policy.py",
                "affected_services": ["Payment Gateway", "Main Database"],
                "business_impact": 40,
                "simulation": "New retry policy deploys → Failed payments retry with backoff → Checkout latency increases slightly",
                "severity": "Medium",
                "rollback": ["Revert to the previous retry policy", "Verify checkout latency returns to baseline"],
                "validation": ["curl -f /payment/health", "kubectl logs -l app=payment", "kubectl get pods"],
                "created_at": (now - timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S")
            }
        }
    ]

# ------------------------------
# DATA FETCHING FUNCTIONS
# ------------------------------
def get_pr_data(limit: int = 20) -> List[Dict]:
    """Get PR data for the frontend."""
    return get_mock_pr_data()

def get_pr_details(pr_number: str) -> Dict:
    """Get detailed analysis for a specific PR."""
    prs = get_pr_data(100)
    for pr in prs:
        if pr["pr"] == pr_number:
            details = pr.get("details", {})
            return {
                "repository": pr.get("repository", "Unknown"),
                "severity": pr.get("severity", "MEDIUM"),
                "impact": pr.get("impact", 50),
                "summary": details.get("simulation", "No analysis available."),
                "changed_files": details.get("changed_files", ["Unknown"]),
                "services": details.get("affected_services", ["Unknown"]),
                "simulation": details.get("simulation", "No simulation available.").split(". ") if details.get("simulation") else ["No simulation available"],
                "rollback": details.get("rollback", ["Rollback not available"]),
                "validation": details.get("validation", ["Validation not available"])
            }
    return DEFAULT_PR_DETAILS

def get_metrics() -> Dict:
    """Calculate metrics from PR data."""
    prs = get_pr_data(100)
    
    total_prs = len(prs)
    high_risk = sum(1 for p in prs if p.get("severity") in ["HIGH", "CRITICAL"])
    
    highest_risk = None
    highest_impact = 0
    for pr in prs:
        impact = pr.get("impact", 0)
        if impact > highest_impact:
            highest_impact = impact
            highest_risk = pr
    
    all_services = []
    for pr in prs:
        details = pr.get("details", {})
        services = details.get("affected_services", [])
        all_services.extend(services)
    most_affected = max(set(all_services), key=all_services.count) if all_services else "None"
    
    repo_counts = {}
    for pr in prs:
        repo = pr.get("repository", "Unknown")
        repo_counts[repo] = repo_counts.get(repo, 0) + 1
    
    return {
        "total_prs": total_prs,
        "high_risk_prs": high_risk,
        "highest_risk_pr": highest_risk,
        "highest_risk_impact": highest_impact,
        "most_affected_service": most_affected,
        "repository_counts": repo_counts
    }

def get_ai_analysis(services: List[str], impact_percentage: int) -> Dict:
    """Get AI analysis for given services."""
    try:
        return generate_insights(services, impact_percentage)
    except Exception as e:
        print(f"⚠️ AI analysis error: {e}")
        return {
            "simulation": f"⚠️ AI analysis unavailable: {e}",
            "severity": "Medium",
            "rollback": ["Try again later"],
            "validation": ["Check system status"],
            "tokens_used": {"total_tokens": 0}
        }

# ------------------------------
# EXPOSE FUNCTIONS FOR FRONTEND
# ------------------------------
__all__ = [
    'get_pr_data',
    'get_pr_details', 
    'get_metrics',
    'get_ai_analysis',
    'SEVERITY_MAP',
    'clear_cache',
    'get_cache_size'
]

# ------------------------------
# TEST
# ------------------------------
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔌 Testing Integration Layer")
    print("="*60 + "\n")
    
    # Test 1: Get PR data
    prs = get_pr_data(5)
    print(f"✅ get_pr_data() returned {len(prs)} PRs")
    
    # Test 2: Get metrics
    metrics = get_metrics()
    print(f"✅ get_metrics() returned {metrics['total_prs']} total PRs")
    
    # Test 3: Get AI analysis
    result = get_ai_analysis(["payment_service", "login_service"], 85)
    print(f"✅ get_ai_analysis() returned severity: {result['severity']}")
    
    print("\n" + "="*60)
    print("✅ Integration Layer Test Complete!")
    print("="*60)